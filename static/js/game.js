let gameId = null;
let currentPlayer = 1;
let ws = null;
let gameStarted = false;
let boardElement = null;
let myPlayerNumber = null;
let movesHistory = [];

// 初始化WebSocket连接
function initWebSocket() {
    ws = new WebSocket(`ws://${window.location.host}/ws/${gameId}`);
    
    ws.onmessage = function(event) {
        const data = JSON.parse(event.data);
        switch(data.type) {
            case 'init':
                handleInitData(data);
                break;
            case 'chat':
                addMessage(data.player, data.message);
                break;
            case 'thinking_start':
                handleThinkingStart(data);
                break;
            case 'move_complete':
                handleMoveComplete(data);
                break;
        }
    };

    ws.onclose = function() {
        console.log('WebSocket连接已关闭');
        setTimeout(initWebSocket, 1000);
    };
}

// 处理初始化数据
function handleInitData(data) {
    const userText = currentPlayer === 1 ? '黑方' : '白方'
    myPlayerNumber = data.player_number;
    updateBoard(data.board);
    updateCurrentPlayer(data.current_player);
    movesHistory = data.moves_history;
    
    const chatMessages = document.getElementById('chatMessages');
    chatMessages.innerHTML = '';
    
    // 显示聊天历史
    data.chat_history.forEach(msg => {
        addMessage(msg.player, msg.message);
    });
    
    if (data.last_move) {
        updateAIReasoning(data.last_move,userText);
    }
    
    console.log(`已连接为玩家${myPlayerNumber} (${myPlayerNumber === 1 ? '黑棋' : '白棋'})`);
    
    if (data.current_player === myPlayerNumber) {
        boardElement.classList.remove('disabled');
    }
}

// 处理AI开始思考的消息
function handleThinkingStart(data) {
    document.getElementById('thinkingIndicator').classList.add('active');
    updateBoard(data.board);
    updateCurrentPlayer(data.current_player);
    movesHistory = data.moves_history;
}

// 处理移动完成的消息
function handleMoveComplete(data) {
    const userText = currentPlayer === 1 ? '黑方' : '白方'
    updateBoard(data.board);
    updateCurrentPlayer(data.current_player);
    movesHistory = data.moves_history;
    
    if (data.last_move) {
        updateAIReasoning(data.last_move,userText);
    }
    document.getElementById('thinkingIndicator').classList.remove('active');
    
    if (data.current_player === myPlayerNumber) {
        boardElement.classList.remove('disabled');
    } else {
        boardElement.classList.add('disabled');
    }
}

// 初始化棋盘
function initBoard() {
    const grid = document.getElementById('grid');
    grid.innerHTML = '';
    
    for (let i = 0; i < 19; i++) {
        for (let j = 0; j < 19; j++) {
            const cell = document.createElement('div');
            cell.className = 'cell';
            cell.dataset.x = j;
            cell.dataset.y = i;
            cell.style.left = (j * 30 + 15) + 'px';
            cell.style.top = (i * 30 + 15) + 'px';
            cell.addEventListener('click', handleCellClick);
            grid.appendChild(cell);
        }
    }
    
    boardElement = document.getElementById('goBoard');
}

// 处理棋子点击事件
function handleCellClick(event) {
    if (!gameStarted || !ws) return;
    
    const x = parseInt(event.target.dataset.x);
    const y = parseInt(event.target.dataset.y);
    
    ws.send(JSON.stringify({
        type: 'move',
        x: x,
        y: y
    }));
    
    boardElement.classList.add('disabled');
}

// 更新棋盘状态
function updateBoard(board) {
    const cells = document.querySelectorAll('.cell');
    cells.forEach(cell => {
        const x = parseInt(cell.dataset.x);
        const y = parseInt(cell.dataset.y);
        
        // 移除现有的棋子
        const existingStone = cell.querySelector('.stone');
        if (existingStone) {
            cell.removeChild(existingStone);
        }
        
        // 添加新棋子
        if (board[y][x] !== 0) {
            const stone = document.createElement('div');
            stone.className = `stone ${board[y][x] === 1 ? 'black' : 'white'}`;
            cell.appendChild(stone);
        }
    });
}

// 更新当前玩家显示
function updateCurrentPlayer(player) {
    currentPlayer = player;
    const indicator = document.getElementById('playerIndicator');
    const currentPlayerText = document.getElementById('currentPlayer');
    
    indicator.className = 'player-indicator ' + (player === 1 ? 'player-black' : 'player-white');
    currentPlayerText.textContent = player === 1 ? '黑方' : '白方';
}

// 更新AI思考过程显示
function updateAIReasoning(last_move,userText) {
    const thinkingHistoryElement = document.getElementById('thinkingHistory');
    reasoning = last_move[2];
    cordinate = [last_move[0],last_move[1]];
    if (!reasoning) {
        return;
    }

    try {
        const timestamp = new Date().toLocaleTimeString();
        
        let html = `
            <div class="thinking-entry">
                <div class="thinking-header">
                    <span class="timestamp">${timestamp}</span>
                    <span class="player">${userText}思考过程</span>
                </div>
                <div class="thinking-content">
                    <div class="content-body">落子坐标：[${cordinate}]：${reasoning}</div>
                </div>
            </div>
        `;
        
        // 将新的思考过程添加到历史记录的底部
        thinkingHistoryElement.insertAdjacentHTML('beforeend', html);
    } catch (error) {
        console.error('更新AI思考过程时出错:', error);
    }
}

// 添加聊天消息
function addMessage(player, message) {
    const chatMessages = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message player${player}`;
    messageDiv.textContent = `${player === 1 ? '黑方' : '白方'}: ${message}`;
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// 发送聊天消息
function sendMessage() {
    const input = document.getElementById('messageInput');
    const message = input.value.trim();
    
    if (message && ws) {
        ws.send(JSON.stringify({
            type: 'chat',
            message: message
        }));
        input.value = '';
    }
}

// 开始新游戏
function startNewGame() {
    const blackModelUrl = document.getElementById('blackModelUrl').value;
    const blackModelName = document.getElementById('blackModelName').value;
    const whiteModelUrl = document.getElementById('whiteModelUrl').value;
    const whiteModelName = document.getElementById('whiteModelName').value;
    
    fetch('/start_game', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            player_type: "ai",
            black_model_url: blackModelUrl,
            black_model_name: blackModelName,
            white_model_url: whiteModelUrl,
            white_model_name: whiteModelName,
            first_player: 1
        })
    })
    .then(response => response.json())
    .then(data => {
        gameId = data.game_id;
        document.getElementById('gameId').textContent = gameId;
        gameStarted = true;
        initBoard();
        initWebSocket();
    })
    .catch(error => {
        console.error('创建新游戏时出错:', error);
        alert('创建新游戏失败，请重试');
    });
}

// 监听回车键发送消息
document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('messageInput').addEventListener('keypress', function(event) {
        if (event.key === 'Enter') {
            sendMessage();
        }
    });
});
