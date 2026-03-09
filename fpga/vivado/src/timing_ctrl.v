/**
 * timing_ctrl.v
 * 
 * DAC-3D时序控制器顶层模块
 * 
 * 功能:
 * - 接收ARM端配置
 * - PSO位置同步输出
 * - PWM触发信号生成
 * - 编码器位置监控
 */

module timing_ctrl #(
    parameter CLK_FREQ = 100_000_000,  // 100MHz系统时钟
    parameter ADDR_WIDTH = 8,
    parameter DATA_WIDTH = 32
)(
    // 时钟和复位
    input wire clk,
    input wire rst_n,
    
    // AXI-Lite从接口(与ARM通信)
    input wire [ADDR_WIDTH-1:0] s_axi_awaddr,
    input wire s_axi_awvalid,
    output wire s_axi_awready,
    
    input wire [DATA_WIDTH-1:0] s_axi_wdata,
    input wire s_axi_wvalid,
    output wire s_axi_wready,
    
    output wire [1:0] s_axi_bresp,
    output wire s_axi_bvalid,
    input wire s_axi_bready,
    
    input wire [ADDR_WIDTH-1:0] s_axi_araddr,
    input wire s_axi_arvalid,
    output wire s_axi_arready,
    
    output wire [DATA_WIDTH-1:0] s_axi_rdata,
    output wire [1:0] s_axi_rresp,
    output wire s_axi_rvalid,
    input wire s_axi_rready,
    
    // 编码器输入(差分信号)
    input wire enc_x_a_p, enc_x_a_n,
    input wire enc_x_b_p, enc_x_b_n,
    input wire enc_y_a_p, enc_y_a_n,
    input wire enc_y_b_p, enc_y_b_n,
    
    // 触发输出
    output wire trig_camera,   // 相机触发
    output wire trig_dmd,      // DMD触发
    output wire trig_led,      // LED触发
    output wire trig_rsv,      // 预留触发
    
    // 状态指示
    output wire busy,
    output wire error
);

    // 寄存器地址定义
    localparam ADDR_CTRL        = 8'h00;
    localparam ADDR_STATUS      = 8'h04;
    localparam ADDR_PSO_START   = 8'h08;
    localparam ADDR_PSO_END     = 8'h0C;
    localparam ADDR_PSO_INTERVAL = 8'h10;
    localparam ADDR_PSO_MODE    = 8'h14;
    localparam ADDR_PWM_PERIOD  = 8'h18;
    localparam ADDR_PWM_DUTY_0  = 8'h1C;
    localparam ADDR_PWM_DUTY_1  = 8'h20;
    localparam ADDR_PWM_DUTY_2  = 8'h24;
    localparam ADDR_ENC_X_POS   = 8'h2C;
    localparam ADDR_ENC_Y_POS   = 8'h30;
    localparam ADDR_FRAME_CNT   = 8'h38;
    localparam ADDR_TIMESTAMP   = 8'h3C;
    localparam ADDR_TRIG_DELAY  = 8'h40;
    localparam ADDR_TRIG_WIDTH  = 8'h44;
    
    // 内部寄存器
    reg [31:0] reg_ctrl;
    reg [31:0] reg_pso_start;
    reg [31:0] reg_pso_end;
    reg [31:0] reg_pso_interval;
    reg [31:0] reg_pso_mode;
    reg [31:0] reg_pwm_period;
    reg [31:0] reg_pwm_duty_0;
    reg [31:0] reg_pwm_duty_1;
    reg [31:0] reg_pwm_duty_2;
    reg [31:0] reg_trig_delay;
    reg [31:0] reg_trig_width;
    
    // 只读寄存器
    wire [31:0] reg_status;
    wire [31:0] reg_enc_x_pos;
    wire [31:0] reg_enc_y_pos;
    wire [31:0] reg_frame_cnt;
    wire [31:0] reg_timestamp;
    
    // 控制信号
    wire global_en = reg_ctrl[0];
    wire soft_reset = reg_ctrl[1];
    wire pso_en = reg_ctrl[2];
    wire arm = reg_ctrl[3];
    
    // 编码器位置
    wire signed [31:0] enc_x_position;
    wire signed [31:0] enc_y_position;
    
    // PSO触发信号
    wire pso_trigger;
    wire pso_active;
    
    // 帧计数
    reg [15:0] frame_counter;
    
    // 时间戳计数器(微秒)
    reg [31:0] timestamp_us;
    reg [6:0] us_counter;
    
    // 状态寄存器
    assign reg_status = {
        frame_counter,      // [31:16] 帧计数
        8'h00,             // [15:8] 保留
        4'h0,              // [7:4] 状态
        1'b0,              // [3] 保留
        pso_active,        // [2] PSO激活
        error,             // [1] 错误
        busy               // [0] 忙碌
    };
    
    assign busy = pso_active;
    assign error = 1'b0;  // TODO: 实现错误检测
    
    // ========== AXI-Lite接口实现 ==========
    
    reg axi_awready_r;
    reg axi_wready_r;
    reg axi_bvalid_r;
    reg axi_arready_r;
    reg [31:0] axi_rdata_r;
    reg axi_rvalid_r;
    
    assign s_axi_awready = axi_awready_r;
    assign s_axi_wready = axi_wready_r;
    assign s_axi_bresp = 2'b00;  // OKAY
    assign s_axi_bvalid = axi_bvalid_r;
    assign s_axi_arready = axi_arready_r;
    assign s_axi_rdata = axi_rdata_r;
    assign s_axi_rresp = 2'b00;  // OKAY
    assign s_axi_rvalid = axi_rvalid_r;
    
    // 写地址通道
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            axi_awready_r <= 1'b0;
        else if (s_axi_awvalid && !axi_awready_r)
            axi_awready_r <= 1'b1;
        else
            axi_awready_r <= 1'b0;
    end
    
    // 写数据通道
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            axi_wready_r <= 1'b0;
        else if (s_axi_wvalid && !axi_wready_r)
            axi_wready_r <= 1'b1;
        else
            axi_wready_r <= 1'b0;
    end
    
    // 写响应通道
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            axi_bvalid_r <= 1'b0;
        else if (axi_awready_r && axi_wready_r)
            axi_bvalid_r <= 1'b1;
        else if (s_axi_bready)
            axi_bvalid_r <= 1'b0;
    end
    
    // 写寄存器
    reg [ADDR_WIDTH-1:0] write_addr;
    
    always @(posedge clk) begin
        if (s_axi_awvalid && axi_awready_r)
            write_addr <= s_axi_awaddr;
    end
    
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            reg_ctrl <= 32'h0;
            reg_pso_start <= 32'h0;
            reg_pso_end <= 32'h0;
            reg_pso_interval <= 32'h0;
            reg_pso_mode <= 32'h0;
            reg_pwm_period <= 32'd10000;  // 默认100kHz
            reg_pwm_duty_0 <= 32'd100;
            reg_pwm_duty_1 <= 32'd100;
            reg_pwm_duty_2 <= 32'd100;
            reg_trig_delay <= 32'h0;
            reg_trig_width <= 32'd100;  // 默认1μs
        end
        else if (soft_reset) begin
            reg_ctrl <= 32'h0;
        end
        else if (s_axi_wvalid && axi_wready_r) begin
            case (write_addr)
                ADDR_CTRL:        reg_ctrl <= s_axi_wdata;
                ADDR_PSO_START:   reg_pso_start <= s_axi_wdata;
                ADDR_PSO_END:     reg_pso_end <= s_axi_wdata;
                ADDR_PSO_INTERVAL: reg_pso_interval <= s_axi_wdata;
                ADDR_PSO_MODE:    reg_pso_mode <= s_axi_wdata;
                ADDR_PWM_PERIOD:  reg_pwm_period <= s_axi_wdata;
                ADDR_PWM_DUTY_0:  reg_pwm_duty_0 <= s_axi_wdata;
                ADDR_PWM_DUTY_1:  reg_pwm_duty_1 <= s_axi_wdata;
                ADDR_PWM_DUTY_2:  reg_pwm_duty_2 <= s_axi_wdata;
                ADDR_TRIG_DELAY:  reg_trig_delay <= s_axi_wdata;
                ADDR_TRIG_WIDTH:  reg_trig_width <= s_axi_wdata;
            endcase
        end
    end
    
    // 读地址通道
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            axi_arready_r <= 1'b0;
        else if (s_axi_arvalid && !axi_arready_r)
            axi_arready_r <= 1'b1;
        else
            axi_arready_r <= 1'b0;
    end
    
    // 读数据通道
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            axi_rdata_r <= 32'h0;
            axi_rvalid_r <= 1'b0;
        end
        else if (s_axi_arvalid && axi_arready_r) begin
            axi_rvalid_r <= 1'b1;
            case (s_axi_araddr)
                ADDR_CTRL:        axi_rdata_r <= reg_ctrl;
                ADDR_STATUS:      axi_rdata_r <= reg_status;
                ADDR_PSO_START:   axi_rdata_r <= reg_pso_start;
                ADDR_PSO_END:     axi_rdata_r <= reg_pso_end;
                ADDR_PSO_INTERVAL: axi_rdata_r <= reg_pso_interval;
                ADDR_PSO_MODE:    axi_rdata_r <= reg_pso_mode;
                ADDR_ENC_X_POS:   axi_rdata_r <= reg_enc_x_pos;
                ADDR_ENC_Y_POS:   axi_rdata_r <= reg_enc_y_pos;
                ADDR_FRAME_CNT:   axi_rdata_r <= reg_frame_cnt;
                ADDR_TIMESTAMP:   axi_rdata_r <= reg_timestamp;
                default:          axi_rdata_r <= 32'hDEADBEEF;
            endcase
        end
        else if (s_axi_rready)
            axi_rvalid_r <= 1'b0;
    end
    
    // ========== 编码器解码器 ==========
    
    encoder_decoder enc_x (
        .clk(clk),
        .rst_n(rst_n && global_en),
        .enc_a_p(enc_x_a_p),
        .enc_a_n(enc_x_a_n),
        .enc_b_p(enc_x_b_p),
        .enc_b_n(enc_x_b_n),
        .position(enc_x_position)
    );
    
    encoder_decoder enc_y (
        .clk(clk),
        .rst_n(rst_n && global_en),
        .enc_a_p(enc_y_a_p),
        .enc_a_n(enc_y_a_n),
        .enc_b_p(enc_y_b_p),
        .enc_b_n(enc_y_b_n),
        .position(enc_y_position)
    );
    
    assign reg_enc_x_pos = enc_x_position;
    assign reg_enc_y_pos = enc_y_position;
    
    // ========== PSO生成器 ==========
    
    pso_generator pso (
        .clk(clk),
        .rst_n(rst_n && global_en),
        .enable(pso_en && arm),
        .position(enc_x_position),
        .start_pos(reg_pso_start),
        .end_pos(reg_pso_end),
        .interval(reg_pso_interval),
        .trigger(pso_trigger),
        .active(pso_active)
    );
    
    // ========== PWM控制器 ==========
    
    wire trig_delayed;
    
    pwm_controller pwm_cam (
        .clk(clk),
        .rst_n(rst_n && global_en),
        .trigger_in(trig_delayed),
        .period(reg_pwm_period),
        .duty(reg_pwm_duty_0),
        .pwm_out(trig_camera)
    );
    
    pwm_controller pwm_dmd (
        .clk(clk),
        .rst_n(rst_n && global_en),
        .trigger_in(trig_delayed),
        .period(reg_pwm_period),
        .duty(reg_pwm_duty_1),
        .pwm_out(trig_dmd)
    );
    
    pwm_controller pwm_led (
        .clk(clk),
        .rst_n(rst_n && global_en),
        .trigger_in(trig_delayed),
        .period(reg_pwm_period),
        .duty(reg_pwm_duty_2),
        .pwm_out(trig_led)
    );
    
    assign trig_rsv = 1'b0;
    
    // ========== 触发延迟 ==========
    
    trigger_delay delay_module (
        .clk(clk),
        .rst_n(rst_n),
        .trigger_in(pso_trigger),
        .delay_cycles(reg_trig_delay),
        .trigger_out(trig_delayed)
    );
    
    // ========== 帧计数器 ==========
    
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n || soft_reset)
            frame_counter <= 16'h0;
        else if (pso_trigger)
            frame_counter <= frame_counter + 1'b1;
    end
    
    assign reg_frame_cnt = {16'h0, frame_counter};
    
    // ========== 时间戳计数器 ==========
    
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n || soft_reset) begin
            timestamp_us <= 32'h0;
            us_counter <= 7'h0;
        end
        else if (global_en) begin
            if (us_counter == (CLK_FREQ/1000000 - 1)) begin
                us_counter <= 7'h0;
                timestamp_us <= timestamp_us + 1'b1;
            end
            else begin
                us_counter <= us_counter + 1'b1;
            end
        end
    end
    
    assign reg_timestamp = timestamp_us;

endmodule
