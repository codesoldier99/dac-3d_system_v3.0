/**
 * pwm_controller.v
 * 
 * PWM控制器
 * 用于生成触发脉冲
 */

module pwm_controller (
    input wire clk,
    input wire rst_n,
    input wire trigger_in,
    input wire [31:0] period,
    input wire [31:0] duty,
    output reg pwm_out
);

    reg [31:0] counter;
    reg triggered;
    
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            counter <= 32'h0;
            pwm_out <= 1'b0;
            triggered <= 1'b0;
        end
        else if (trigger_in && !triggered) begin
            // 触发开始
            triggered <= 1'b1;
            counter <= 32'h0;
            pwm_out <= 1'b1;
        end
        else if (triggered) begin
            counter <= counter + 1'b1;
            
            if (counter >= duty)
                pwm_out <= 1'b0;
            
            if (counter >= period) begin
                triggered <= 1'b0;
                counter <= 32'h0;
            end
        end
        else begin
            pwm_out <= 1'b0;
        end
    end

endmodule
