import aiohttp
import json
import asyncio
import logging
import re
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger('go_game')

def extract_json_from_markdown(text: str) -> str:
    """从Markdown文本中提取JSON内容"""
    # 匹配```json和```之间的内容，或者```和```之间的内容
    json_pattern = r"```(?:json)?\n([\s\S]*?)\n```"
    matches = re.findall(json_pattern, text)
    
    if matches:
        return matches[0].strip()
    return text.strip()

def format_board_state(board: List[List[int]]) -> str:
    """格式化棋盘状态，使其更易读"""
    formatted = "当前棋盘状态：\n\n"
    formatted += "   " + " ".join(f"{i:2d}" for i in range(19)) + "\n"
    for i, row in enumerate(board):
        formatted += f"{i:2d} "
        formatted += " ".join(
            "●" if cell == 1 else "○" if cell == 2 else "·"
            for cell in row
        )
        formatted += "\n"
    return formatted

def format_moves_history(moves: List[Tuple[int, int, int]]) -> str:
    """格式化移动历史"""
    if not moves:
        return "暂无历史移动"
    
    formatted = "历史移动记录：\n"
    for x, y, player in moves:
        color = "黑棋" if player == 1 else "白棋"
        formatted += f"- {color}：({x}, {y})\n"
    return formatted

def format_chat_history(chat_history: Optional[List[Dict]]) -> str:
    """格式化聊天历史"""
    if not chat_history:
        return ""
    
    formatted = "\n最近对话记录：\n"
    for msg in chat_history[:5]:  # 只显示最近5条消息
        player = "黑方" if msg["player"] == 1 else "白方"
        formatted += f"- {player}：{msg['message']}\n"
    return formatted

class AIPlayer:
    def __init__(self, api_url="http://ip:port/v1/chat/completions", model_name="DeepSeek-R1"):
        self.api_url = api_url
        self.model_name = model_name
        self.headers = {
            'Content-Type': 'application/json'
        }
        logger.info(f"初始化AI玩家，API地址: {api_url}")

    def _format_board(self, board):
        """将棋盘转换为字符串表示"""
        symbols = {0: ".", 1: "●", 2: "○"}
        board_str = "当前棋盘状态：\n"
        # 添加列标签
        board_str += "   " + " ".join([f"{i:2}" for i in range(19)]) + "\n"
        for i, row in enumerate(board):
            # 添加行标签
            board_str += f"{i:2} "
            board_str += " ".join([symbols[cell] for cell in row]) + "\n"
        return board_str

    def _format_chat_history(self, chat_history):
        """格式化聊天历史"""
        if not chat_history:
            return ""
        
        chat_str = "\n最近的对话：\n"
        for msg in chat_history:  # 只显示最近5条消息
            player = "黑方" if msg["player"] == 1 else "白方"
            chat_str += f"{player}: {msg['message']}\n"
        return chat_str

    def _create_prompt(self, board, current_player, moves_history, chat_history=None):
        """创建AI提示词"""
        prompt = f"""我是一名围棋战术家，我的棋风以凌厉攻势著称，现在需要撕开对手防线。

{format_board_state(board)}

此刻轮到我执{'黑' if current_player == 1 else '白'}发起致命打击。

{format_moves_history(moves_history)}

{format_chat_history(chat_history)}

我将执行：
1. 闪电战局扫描 - 5秒内定位敌方最薄弱环节
2. 死亡交叉分析 - 找出可同时威胁两个弱点的穿刺点
3. 窒息战术选择 - 优先考虑能持续压缩对手生存空间的落点

必须满足以下战争准则：
1. 落子必须产生至少两个后续杀招威胁
2. 优先阻断敌方大龙连接通道
3. 当存在劫争可能时，主动制造战争迷雾
4. 不能在已经存在棋子的地方落子

立即输出作战方案：
{{
"move": [x,y], // 落子位置坐标
"reasoning": "...", // 简明扼要的斩首战术说明（使用军事术语，如"钳形攻势/纵深突破"）
"pressure_index": 0-100 // 计算该落子对敌方造成的心理压迫值
}}

血腥法则：

1. 禁止任何防御性布阵
2. 若存在同价值目标，选择使对手最痛苦的落点
3. 当棋盘有血迹（吃子痕迹）时，必须持续扩大战果
"""
        prompt2 = f"""我是一位围棋大师，让我仔细思考下一步棋该如何落子。

{format_board_state(board)}

现在轮到我下{'黑棋' if current_player == 1 else '白棋'}了。

{format_moves_history(moves_history)}

{format_chat_history(chat_history)}

我需要：
1. 仔细评估当前局势
2. 分析对手的意图和动向
3. 制定整体战略部署

我会以JSON格式表达我的思考结果：
{{
    "move": [x, y],     // x,y为0-18的整数，表示我决定落子的坐标
    "reasoning": "..."  // 我为什么选择这个位置（以第一人称表述，如"我选择这里是因为..."）
}}

注意事项：
- 确保我选择的位置是空位
- 认真思考对手之前的对话（如果有）
- 清晰地解释我的战术分析
"""
        return prompt

    async def get_move(self, board, current_player, moves_history, chat_history=None):
        """获取AI的下一步移动"""
        prompt = self._create_prompt(board, current_player, moves_history, chat_history)
        logger.info(f"AI提示词: {prompt}")
        
        request_data = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "frequency_penalty": 0,
            "max_tokens": 8192,
            "presence_penalty": 0,
            "response_format": {
                "type": "text"
            },
            "stop": None,
            "stream": False,
            "stream_options": None,
            "temperature": 1,
            "top_p": 1,
            "tools": None,
            "tool_choice": "none",
            "logprobs": False,
            "top_logprobs": None
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url,
                    headers=self.headers,
                    json=request_data
                ) as response:
                    if response.status != 200:
                        logger.error(f"API请求失败: {response.status}")
                        raise Exception(f"API请求失败: {response.status}")
                    
                    result = await response.json()
                    logger.info(f"AI响应: {result}")
                    
                    # 提取AI响应内容
                    ai_response = result['choices'][0]['message']['content']
                    
                    # 从Markdown中提取JSON并解析
                    try:
                        json_str = extract_json_from_markdown(ai_response)
                        logger.info(f"提取的JSON字符串：\n{json_str}")
                        move_data = json.loads(json_str)
                        x, y = move_data['move']
                        reasoning = move_data.get('reasoning', '无解释')
                        # 验证坐标是否有效
                        if not (0 <= x < 19 and 0 <= y < 19):
                            raise ValueError("无效的坐标范围")
                        
                        # 验证位置是否已被占用
                        if board[y][x] != 0:
                            raise ValueError("该位置已被占用")
                        
                        logger.info(f"AI决定在 ({x}, {y}) 落子，原因: {reasoning}")
                        return x, y, reasoning
                        
                    except json.JSONDecodeError:
                        logger.error("AI返回的响应格式无效")
                        raise Exception("AI返回的响应格式无效")
                    except (KeyError, ValueError) as e:
                        logger.error(f"AI返回的移动无效: {str(e)}")
                        raise Exception(f"AI返回的移动无效: {str(e)}")
                        
        except Exception as e:
            logger.error(f"获取AI移动时出错: {str(e)}")
            # 在出错时返回一个随机的有效移动
            import random
            empty_positions = [
                (x, y) for x in range(19) for y in range(19)
                if board[y][x] == 0
            ]
            if empty_positions:
                x, y = random.choice(empty_positions)
                logger.warning(f"使用随机移动: ({x}, {y})")
                return x, y, "抱歉，我遇到了一些问题，所以这一手我选择了一个随机的位置"
            return None, None, "我发现已经没有可以落子的位置了"
