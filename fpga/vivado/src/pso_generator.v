/**
 * pso_generator.v
 * 
 * PSO(位置同步输出)生成器
 * 
 * 功能: 根据编码器位置自动生成触发脉冲
 */

module pso_generator (
    input wire clk,
    input wire rst_n,
    input wire enable,
    
    input wire signed [31:0] position,      // 当前位置
    input wire signed [31:0] start_pos,     // 起始位置
    input wire signed [31:0] end_pos,       // 结束位置
    input wire [31:0] interval,             // 触发间隔
    
    output reg trigger,
    output reg active
);

    reg signed [31:0] next_trigger_pos;
    reg signed [31:0] last_position;
    
    wire signed [31:0] pos_delta = position - last_position;
    wire in_range = (position >= start_pos) && (position <= end_pos);
    wire at_trigger = (position >= next_trigger_pos) && (pos_delta > 0);
    
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            trigger <= 1'b0;
            active <= 1'b0;
            next_trigger_pos <= 32'sd0;
            last_position <= 32'sd0;
        end
        else if (!enable) begin
            trigger <= 1'b0;
            active <= 1'b0;
            next_trigger_pos <= start_pos;
            last_position <= position;
        end
        else begin
            last_position <= position;
            
            if (!active && in_range) begin
                // 进入扫描范围
                active <= 1'b1;
                next_trigger_pos <= start_pos;
            end
            else if (active && !in_range) begin
                // 离开扫描范围
                active <= 1'b0;
                trigger <= 1'b0;
            end
            else if (active && at_trigger) begin
                // 到达触发位置
                trigger <= 1'b1;
                next_trigger_pos <= next_trigger_pos + interval;
            end
            else begin
                trigger <= 1'b0;
            end
        end
    end

endmodule
