from fastapi import FastAPI, HTTPException, WebSocket, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Tuple
import uuid
import asyncio
import json
from ai_player import AIPlayer
from logger_config import setup_logger

# 设置日志记录器
logger = setup_logger()

app = FastAPI(title="围棋对战API")
app.mount("/static", StaticFiles(directory="static"), name="static")

# 定义棋盘大小
BOARD_SIZE = 19

class GameState:
    def __init__(self, black_model_url=None, black_model_name=None, white_model_url=None, white_model_name=None, first_player=1):
        self.board = [[0 for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
        self.current_player = first_player  # 1代表黑棋，2代表白棋
        self.game_id = str(uuid.uuid4())
        self.moves_history = []
        self.chat_history = []
        self.black_model_url = black_model_url
        self.white_model_url = white_model_url
        self.black_ai = AIPlayer(api_url=black_model_url, model_name=black_model_name) if black_model_url else None
        self.white_ai = AIPlayer(api_url=white_model_url, model_name=white_model_name) if white_model_url else None
        self.last_move: Optional[Tuple[int, int, str]] = None  # (x, y, reasoning)
        self.current_thinking = ""  # 当前棋手的思考过程
        logger.info(f"创建新游戏 {self.game_id}, 黑方模型: {black_model_url}, 白方模型: {white_model_url}, 先手: {'黑方' if first_player == 1 else '白方'}")

    def is_valid_move(self, x: int, y: int) -> bool:
        if not (0 <= x < BOARD_SIZE and 0 <= y < BOARD_SIZE):
            return False
        if self.board[y][x] != 0:
            return False
        return True

    def make_move(self, x: int, y: int) -> bool:
        if not self.is_valid_move(x, y):
            logger.warning(f"游戏 {self.game_id}: 无效的移动 ({x}, {y})")
            return False
        
        self.board[y][x] = self.current_player
        self.moves_history.append((x, y, self.current_player))
        logger.info(f"游戏 {self.game_id}: {'黑方' if self.current_player == 1 else '白方'} 在 ({x}, {y}) 落子")
        self.current_player = 3 - self.current_player  # 切换玩家（1->2或2->1）
        self.current_thinking = ""  # 清空上个棋手的思考过程
        return True

    def get_board_state(self) -> List[List[int]]:
        return self.board

    def get_current_player(self) -> int:
        return self.current_player

# 存储游戏状态
games = {}

class MoveRequest(BaseModel):
    game_id: Optional[str] = None
    x: int
    y: int
    expected_format: Optional[str] = "json"  # 支持不同的返回格式

class GameResponse(BaseModel):
    game_id: str
    board: List[List[int]]
    current_player: int
    message: str
    status: str

class GameConfig(BaseModel):
    player_type: str = "ai"  # "ai" 或 "human"
    black_model_url: Optional[str] = None
    black_model_name: Optional[str] = None
    white_model_url: Optional[str] = None
    white_model_name: Optional[str] = None
    first_player: Optional[int] = 1  # 1代表黑棋，2代表白棋

@app.post("/start_game")
async def start_game(config: GameConfig, background_tasks: BackgroundTasks):
    """
    开始新游戏
    """
    logger.info(f"开始新游戏，配置: {config.dict()}")
    game = GameState(
        black_model_url=config.black_model_url,
        black_model_name=config.black_model_name,
        white_model_url=config.white_model_url,
        white_model_name=config.white_model_name,
        first_player=config.first_player
    )
    games[game.game_id] = game
    
    # 如果是AI对战且当前玩家有AI，立即让AI走第一步
    if config.player_type == "ai" and (
        (game.current_player == 1 and game.black_ai) or 
        (game.current_player == 2 and game.white_ai)
    ):
        background_tasks.add_task(ai_move, game.game_id)
    
    return {
        "game_id": game.game_id,
        "message": "游戏已创建",
        "board": game.get_board_state(),
        "current_player": game.get_current_player(),
        "last_move": game.last_move
    }

async def ai_move(game_id: str):
    """AI走棋"""
    game = games.get(game_id)
    if not game:
        logger.error(f"游戏 {game_id} 不存在")
        return
    
    current_ai = game.black_ai if game.current_player == 1 else game.white_ai
    if not current_ai:
        logger.warning(f"游戏 {game_id}: 当前玩家没有配置AI模型")
        return

    logger.info(f"游戏 {game_id}: AI开始思考...")
    
    # 通知所有连接的客户端AI开始思考
    if game_id in websocket_connections:
        message = {
            "type": "thinking_start",
            "player": game.current_player,
            "board": game.get_board_state(),
            "current_player": game.get_current_player(),
            "moves_history": game.moves_history
        }
        await broadcast_message(game_id, message)
    
    # 获取AI的移动
    x, y, reasoning = await current_ai.get_move(
        game.get_board_state(),
        game.get_current_player(),
        game.moves_history,
        game.chat_history
    )
    
    if x is not None and y is not None:
        # 记录当前玩家编号，用于后续通知
        current_player = game.current_player
        
        game.make_move(x, y)
        game.last_move = (x, y, reasoning)
        game.current_thinking = reasoning
        
        # 将思考过程添加到聊天历史
        chat_data = {
            "type": "chat",
            "player": current_player,  # 使用当前玩家的编号
            "message": f"{reasoning}"
        }
        game.chat_history.append(chat_data)
        
        # 通知所有连接的客户端移动完成
        move_message = {
            "type": "move_complete",
            "board": game.get_board_state(),
            "current_player": game.get_current_player(),
            "last_move": game.last_move,
            "thinking": game.current_thinking,
            "chat_history": game.chat_history,
            "moves_history": game.moves_history
        }
        await broadcast_message(game_id, move_message)
        
        # 如果下一个玩家也是AI，则自动触发AI移动
        next_ai = game.black_ai if game.current_player == 1 else game.white_ai
        if next_ai:
            await asyncio.sleep(1)  # 添加短暂延迟，使界面更新更自然
            await ai_move(game_id)

@app.post("/make_move")
async def make_move(move: MoveRequest, background_tasks: BackgroundTasks):
    """
    在指定位置落子
    """
    if not move.game_id or move.game_id not in games:
        raise HTTPException(status_code=404, detail="游戏不存在")

    game = games[move.game_id]
    
    # 处理特殊的AI触发请求
    if move.x == -1 and move.y == -1:
        background_tasks.add_task(ai_move, game.game_id)
        return {
            "game_id": game.game_id,
            "board": game.get_board_state(),
            "current_player": game.get_current_player(),
            "message": "已触发AI移动",
            "status": "success",
            "last_move": game.last_move
        }
    
    if not game.make_move(move.x, move.y):
        raise HTTPException(status_code=400, detail="无效的移动")

    # 通知所有连接的客户端移动完成
    move_message = {
        "type": "move_complete",
        "board": game.get_board_state(),
        "current_player": game.get_current_player(),
        "last_move": game.last_move,
        "thinking": game.current_thinking,
        "chat_history": game.chat_history,
        "moves_history": game.moves_history
    }
    background_tasks.add_task(broadcast_message, game.game_id, move_message)

    # 如果下一个玩家是AI，自动触发AI移动
    next_ai = game.black_ai if game.current_player == 1 else game.white_ai
    if next_ai:
        background_tasks.add_task(ai_move, game.game_id)

    response_data = {
        "game_id": game.game_id,
        "board": game.get_board_state(),
        "current_player": game.get_current_player(),
        "message": f"移动成功: ({move.x}, {move.y})",
        "status": "success",
        "last_move": game.last_move
    }

    # 根据请求的格式返回不同形式的响应
    if move.expected_format == "text":
        board_str = "\n".join([" ".join(map(str, row)) for row in game.get_board_state()])
        return f"Game ID: {game.game_id}\nBoard State:\n{board_str}\nCurrent Player: {game.get_current_player()}"
    
    return GameResponse(**response_data)

@app.get("/game_state/{game_id}")
async def get_game_state(game_id: str):
    """
    获取当前游戏状态
    """
    if game_id not in games:
        raise HTTPException(status_code=404, detail="游戏不存在")
    
    game = games[game_id]
    return {
        "game_id": game_id,
        "board": game.get_board_state(),
        "current_player": game.get_current_player()
    }

# 存储WebSocket连接，包含玩家身份信息
websocket_connections: Dict[str, Dict[WebSocket, int]] = {}  # {game_id: {websocket: player_number}}

async def broadcast_message(game_id: str, message: dict):
    """广播消息给指定游戏的所有连接的客户端"""
    if game_id in websocket_connections:
        for conn in websocket_connections[game_id].keys():
            try:
                await conn.send_json(message)
            except:
                logger.error(f"发送消息到WebSocket失败")

@app.get("/")
async def root():
    return FileResponse('static/index.html')

@app.websocket("/ws/{game_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str):
    await websocket.accept()
    logger.info(f"新的WebSocket连接: 游戏 {game_id}")
    
    if game_id not in websocket_connections:
        websocket_connections[game_id] = {}
    
    # 分配玩家编号（1为黑棋，2为白棋）
    player_number = 1 if len(websocket_connections[game_id]) == 0 else 2
    websocket_connections[game_id][websocket] = player_number
    
    # 发送初始化数据给新连接的玩家
    game = games.get(game_id)
    if game:
        init_data = {
            "type": "init",
            "player_number": player_number,
            "board": game.get_board_state(),
            "current_player": game.get_current_player(),
            "moves_history": game.moves_history,
            "chat_history": game.chat_history,
            "last_move": game.last_move
        }
        await websocket.send_json(init_data)
    
    try:
        while True:
            data = await websocket.receive_json()
            if data["type"] == "chat":
                player_number = websocket_connections[game_id][websocket]
                message = {
                    "type": "chat",
                    "player": player_number,
                    "message": data["message"]
                }
                # 保存聊天记录
                game = games.get(game_id)
                if game:
                    game.chat_history.append(message)
                    logger.info(f"游戏 {game_id}: 新的聊天消息 - {message}")
                
                # 广播消息给所有连接的客户端
                await broadcast_message(game_id, message)
    except Exception as e:
        logger.error(f"WebSocket错误: {str(e)}")
        if websocket in websocket_connections[game_id]:
            del websocket_connections[game_id][websocket]
        if not websocket_connections[game_id]:
            del websocket_connections[game_id]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
