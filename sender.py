import socket
import json
import os
import hashlib
import dotenv

dotenv.load_dotenv()


def start_client(config_file, server_ip, port=int(os.getenv("port_sender"))):
    # Load local config
    with open(config_file, 'r') as f:
        local_config = json.load(f)
    
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((server_ip, int(os.getenv("port_receiver"))))
    print(f"Connected to {server_ip}:{port}")
    
    # Exchange configs
    remote_config = json.loads(s.recv(4096).decode())
    s.send(json.dumps(local_config).encode())
    
    files_to_send, files_to_receive = compare_configs(local_config, remote_config)
    
    # Send files
    for filepath in files_to_send:
        print(f"Sending: {filepath}")
        s.recv(5)  # Wait for READY signal
        
        with open(filepath, 'rb') as f:
            while True:
                data = f.read(1024)
                if not data:
                    break
                s.send(data)
        s.send(b"EOF")
        print(f"Sent: {filepath}")
    
    s.close()


