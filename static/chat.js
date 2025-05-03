<script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>

const socket = io();
socket.emit('join');

function sendMessage() {
  const input = document.getElementById('messageInput');
  if (input.value.trim()) {
    socket.emit('send message', input.value);
    input.value = '';
  }
}
socket.on('chat message', data => {
  const div = document.createElement('div');
  div.textContent = data.msg;
  document.getElementById('messages').appendChild(div);
});
