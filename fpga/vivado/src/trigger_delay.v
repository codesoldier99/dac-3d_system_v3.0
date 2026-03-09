/**
 * trigger_delay.v
 * 
 * 触发延迟模块
 * 用于补偿系统延迟
 */

module trigger_delay (
    input wire clk,
    input wire rst_n,
    input wire trigger_in,
    input wire [31:0] delay_cycles,
    output reg trigger_out
);

    reg [31:0] delay_counter;
    reg delaying;
    
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            delay_counter <= 32'h0;
            trigger_out <= 1'b0;
            delaying <= 1'b0;
        end
        else if (trigger_in && !delaying) begin
            if (delay_cycles == 0) begin
                trigger_out <= 1'b1;
            end
            else begin
                delaying <= 1'b1;
                delay_counter <= 32'h0;
            end
        end
        else if (delaying) begin
            delay_counter <= delay_counter + 1'b1;
            
            if (delay_counter >= delay_cycles) begin
                trigger_out <= 1'b1;
                delaying <= 1'b0;
            end
        end
        else begin
            trigger_out <= 1'b0;
        end
    end

endmodule
