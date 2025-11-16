import socket
import json
import os

def start_server(config_file, port=5000):
    # Load local config
    with open(config_file, 'r') as f:
        local_config = json.load(f)
    
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('0.0.0.0', port))
    s.listen(1)
    print(f"Server listening on port {port}...")
    
    conn, addr = s.accept()
    print(f"Connected by {addr}")
    
    # Exchange configs
    conn.send(json.dumps(local_config).encode())
    remote_config = json.loads(conn.recv(4096).decode())
    
    files_to_send, files_to_receive = compare_configs(local_config, remote_config)
    
    # Receive files
    for filepath in files_to_receive:
        print(f"Receiving: {filepath}")
        conn.send(b"READY")
        
        # Create directories if needed
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        with open(filepath, 'wb') as f:
            while True:
                data = conn.recv(1024)
                if data == b"EOF":
                    break
                f.write(data)
        print(f"Received: {filepath}")
    
    conn.close()
    s.close()
