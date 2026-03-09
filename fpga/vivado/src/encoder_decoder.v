/**
 * encoder_decoder.v
 * 
 * 增量式编码器解码器(4倍频)
 */

module encoder_decoder (
    input wire clk,
    input wire rst_n,
    
    // 差分信号输入
    input wire enc_a_p,
    input wire enc_a_n,
    input wire enc_b_p,
    input wire enc_b_n,
    
    // 位置输出
    output reg signed [31:0] position
);

    // 差分转单端
    wire enc_a = enc_a_p;  // 简化处理，实际应使用IBUFDS
    wire enc_b = enc_b_p;
    
    // A/B信号同步
    reg [2:0] enc_a_sync;
    reg [2:0] enc_b_sync;
    
    always @(posedge clk) begin
        enc_a_sync <= {enc_a_sync[1:0], enc_a};
        enc_b_sync <= {enc_b_sync[1:0], enc_b};
    end
    
    wire enc_a_stable = enc_a_sync[2];
    wire enc_b_stable = enc_b_sync[2];
    
    // 边沿检测
    reg enc_a_d, enc_b_d;
    always @(posedge clk) begin
        enc_a_d <= enc_a_stable;
        enc_b_d <= enc_b_stable;
    end
    
    wire enc_a_rise = enc_a_stable && !enc_a_d;
    wire enc_a_fall = !enc_a_stable && enc_a_d;
    wire enc_b_rise = enc_b_stable && !enc_b_d;
    wire enc_b_fall = !enc_b_stable && enc_b_d;
    
    // 方向判断和计数(4倍频)
    wire count_up = (enc_a_rise && enc_b_stable) || 
                    (enc_a_fall && !enc_b_stable) ||
                    (enc_b_rise && !enc_a_stable) ||
                    (enc_b_fall && enc_a_stable);
                    
    wire count_down = (enc_a_rise && !enc_b_stable) ||
                      (enc_a_fall && enc_b_stable) ||
                      (enc_b_rise && enc_a_stable) ||
                      (enc_b_fall && !enc_a_stable);
    
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            position <= 32'sd0;
        else if (count_up)
            position <= position + 1'b1;
        else if (count_down)
            position <= position - 1'b1;
    end

endmodule
