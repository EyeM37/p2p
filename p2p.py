import socket
import threading
import json
import sys
import os
import secrets

""" การรันโปรแกรมบนสองเครื่อง:
บนเครื่องแรก: python p2p.py 5000
บนเครื่องที่สอง: python p2p.py 5001
ใช้ตัวเลือกที่ 1 บนเครื่องใดเครื่องหนึ่งเพื่อเชื่อมต่อกับอีกเครื่อง """

class Node:
    def __init__(self, host, port):
        self.host = host # กำหนดค่า host ให้กับโหนดนี้
        self.port = port # กำหนดค่า port ให้กับโหนดนี้
        self.peers = []  # เก็บรายการ socket ของ peer ที่เชื่อมต่อ
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) #สร้างซ็อกเก็ต TCP โดยใช้ IPv4 (AF_INET)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) #ตั้งค่า socket option เพื่อให้สามารถใช้พอร์ตซ้ำได้หลังจากการปิดการเชื่อมต่อ
        self.transactions = []  # เก็บรายการ transactions
        self.transaction_file = f"transactions_{port}.json"  # ไฟล์สำหรับบันทึก transactions
        self.wallet_address = self.generate_wallet_address()  # สร้าง wallet address สำหรับโหนดนี้

    def generate_wallet_address(self):
        # สร้าง wallet address แบบง่ายๆ (ในระบบจริงจะซับซ้อนกว่านี้มาก)
        return '0x' + secrets.token_hex(20)

    def start(self):
        # เริ่มต้นการทำงานของโหนด
        self.socket.bind((self.host, self.port)) #ผูกซ็อกเก็ตกับโฮสต์และพอร์ตที่ระบุ
        self.socket.listen(1) #ฟังการเชื่อมต่อที่เข้ามา
        print(f"Node listening on {self.host}:{self.port}") #แสดงโหนดที่กำลังฟังการเชื่อมต่อบนโฮสต์และพอร์ตที่ระบุ
        print(f"Your wallet address is: {self.wallet_address}") #แสดงที่อยู่กระเป๋าเงิน
        self.load_transactions()  # โหลด transactions จากไฟล์ (ถ้ามี)

        # เริ่ม thread สำหรับรับการเชื่อมต่อใหม่
        accept_thread = threading.Thread(target=self.accept_connections)
        accept_thread.start()

    def accept_connections(self):
        while True:
            # รอรับการเชื่อมต่อใหม่
            client_socket, address = self.socket.accept() #รอรับการเชื่อมต่อจาก client เมื่อมี client ใหม่เชื่อมต่อเข้ามา เมธอด accept จะคืนค่าซ็อกเก็ตใหม่ (client_socket) และที่อยู่ของ client (address)
            print(f"New connection from {address}") #แสดงข้อความว่าได้มีการเชื่อมต่อใหม่เข้ามาจากที่อยู่ของ client นั้น

            # เริ่ม thread ใหม่สำหรับจัดการการเชื่อมต่อนี้
            client_thread = threading.Thread(target=self.handle_client, args=(client_socket,))
            client_thread.start()

    def handle_client(self, client_socket):
        while True:
            try:
                # รับข้อมูลจาก client
                data = client_socket.recv(1024) #รอรับข้อมูลจาก client โดยอ่านสูงสุด 1024 ไบต์จากซ็อกเก็ต
                if not data:
                    break #ถ้าไม่ได้รับข้อมูล ให้หยุดลูปด้วยคำสั่ง break
                message = json.loads(data.decode('utf-8')) #ถอดรหัสข้อมูลจากไบต์เป็นสตริงโดยใช้ utf-8 แปลงข้อมูลที่ได้รับมาเป็นพจนานุกรม โดยใช้ json.loads
                
                self.process_message(message) #เรียกฟังก์ชัน process_message เพื่อประมวลผลข้อความที่ได้รับจาก client

            except Exception as e:
                print(f"Error handling client: {e}")
                break #มีข้อผิดพลาด แสดงข้อผิดพลาดในคอนโซล และหยุดการทำงาน

        client_socket.close() #ปิดซ็อกเก็ตของ client เมื่อออกจากลูป

    def connect_to_peer(self, peer_host, peer_port):
        try:
            # สร้างการเชื่อมต่อไปยัง peer
            peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) #สร้าง socket ใหม่สำหรับเชื่อมต่อกับ peer ใช้ IPv4 (AF_INET) และโปรโตคอล TCP (SOCK_STREAM)
            peer_socket.connect((peer_host, peer_port)) #เชื่อมต่อกับ peer โดยใช้ที่อยู่ IP (peer_host) และพอร์ต (peer_port)
            self.peers.append(peer_socket) #เพิ่ม socket ที่เชื่อมต่อกับ peer ลงในรายการ peers ของโหนด
            print(f"Connected to peer {peer_host}:{peer_port}") #แสดงข้อความว่าได้เชื่อมต่อกับ peer สำเร็จแล้ว

            # เริ่ม thread สำหรับรับข้อมูลจาก peer นี้
            peer_thread = threading.Thread(target=self.handle_client, args=(peer_socket,))
            peer_thread.start()

        except Exception as e:
            print(f"Error connecting to peer: {e}") #มีข้อผิดพลาด แสดงข้อผิดพลาดในคอนโซล

    def broadcast(self, message):
        # ส่งข้อมูลไปยังทุก peer ที่เชื่อมต่ออยู่
        for peer_socket in self.peers:
            try:
                peer_socket.send(json.dumps(message).encode('utf-8')) #แปลง message เป็น JSON สตริงโดยใช้ json.dumps เข้ารหัส JSON สตริงเป็นไบต์โดยใช้ utf-8 ส่งไบต์ที่เข้ารหัสแล้วไปยัง peer ผ่านซ็อกเก็ตโดยใช้เมธอด send
            except Exception as e:
                print(f"Error broadcasting to peer: {e}")
                self.peers.remove(peer_socket) #มีข้อผิดพลาด แสดงข้อผิดพลาด และลบซ็อกเก็ตของ peer ออกจากรายการ peers

    def process_message(self, message):
        # ประมวลผลข้อความที่ได้รับ
        if message['type'] == 'transaction': #ตรวจสอบประเภทของข้อความว่ามีค่าเป็น 'transaction' หรือไม่
            print(f"Received transaction: {message['data']}") #แสดงข้อความว่ามีการรับ transaction พร้อมกับข้อมูลของ transaction นั้น
            self.add_transaction(message['data']) #เรียกฟังก์ชัน add_transaction เพื่อเพิ่ม transaction ที่ได้รับเข้าไปในรายการ transactions ของโหนด
        else:
            print(f"Received message: {message}") #หากไม่ใช่ให้แสดงข้อความว่ามีการรับข้อความ พร้อมกับข้อความนั้น

    def add_transaction(self, transaction):
        # เพิ่ม transaction ใหม่และบันทึกลงไฟล์
        self.transactions.append(transaction) #เพิ่ม transaction เข้าไปในรายการ transactions
        self.save_transactions() #บันทึก transactions ลงในไฟล์
        print(f"Transaction added and saved: {transaction}") #แสดงข้อความว่า transaction ถูกเพิ่มและบันทึกลงไฟล์สำเร็จ พร้อมแสดง transaction

    def create_transaction(self, recipient, amount):
        # สร้าง transaction ใหม่
        transaction = {
            'sender': self.wallet_address, #ที่อยู่กระเป๋าเงินของผู้ส่ง
            'recipient': recipient, #ที่อยู่กระเป๋าเงินของผู้รับ
            'amount': amount #จำนวนเงินที่ต้องการส่ง
        }
        self.add_transaction(transaction) #เพิ่ม transaction เข้าไปในรายการ transactions ของโหนดปัจจุบัน
        self.broadcast({'type': 'transaction', 'data': transaction}) #กระจายข้อมูล transaction ไปยังโหนดทุกตัวที่เชื่อมต่ออยู่

    def save_transactions(self):
        # บันทึก transactions ลงไฟล์
        with open(self.transaction_file, 'w') as f: #เปิดไฟล์สำหรับเขียน (โดยลบข้อมูลเก่าทิ้ง)
            json.dump(self.transactions, f) #ใช้ JSON สำหรับเขียนข้อมูล transactions ลงไฟล์

    def load_transactions(self):
        # โหลด transactions จากไฟล์ (ถ้ามี)
        if os.path.exists(self.transaction_file): # ตรวจสอบว่าไฟล์ธุรกรรมอยู่หรือไม่
            with open(self.transaction_file, 'r') as f: # เปิดไฟล์เพื่ออ่านข้อมูล
                self.transactions = json.load(f) # โหลดข้อมูลธุรกรรมจากไฟล์ JSON และเก็บไว้ใน self.transactions
            print(f"Loaded {len(self.transactions)} transactions from file.") # แสดงข้อความว่าโหลดข้อมูลธุรกรรมสำเร็จพร้อมจำนวนข้อมูลที่โหลดได้

if __name__ == "__main__":
    if len(sys.argv) != 2: # ตรวจสอบว่ามีการส่งอาร์กิวเมนต์พอร์ตผ่านบรรทัดคำสั่งมาหรือไม่
        print("Usage: python p2p.py <port>") #แสดงข้อความการใช้งานที่ถูกต้อง
        sys.exit(1) # ออกจากโปรแกรมหากไม่มีอาร์กิวเมนต์พอร์ต
    
    port = int(sys.argv[1]) # แปลงอาร์กิวเมนต์พอร์ตจากสตริงเป็นจำนวนเต็ม
    node = Node("0.0.0.0", port)  # ใช้ "0.0.0.0" เพื่อรับการเชื่อมต่อจากภายนอก
    node.start() # เริ่มต้นการทำงานของโหนด
    
    while True:
        print("\n1. Connect to a peer") # แสดงตัวเลือกการเชื่อมต่อกับ peer
        print("2. Create a transaction") # แสดงตัวเลือกการสร้างธุรกรรม
        print("3. View all transactions") # แสดงตัวเลือกการดูธุรกรรมทั้งหมด
        print("4. View my wallet address") # แสดงตัวเลือกการดูที่อยู่กระเป๋าเงินของตนเอง
        print("5. Exit") # แสดงตัวเลือกการออกจากโปรแกรม
        choice = input("Enter your choice: ") # รับการเลือกของผู้ใช้จาก input
        
        if choice == '1': #หากเลือก 1 
            peer_host = input("Enter peer host to connect: ") # รับข้อมูล peer host ที่ต้องการเชื่อมต่อ
            peer_port = int(input("Enter peer port to connect: ")) # รับข้อมูล peer port ที่ต้องการเชื่อมต่อและแปลงเป็นจำนวนเต็ม
            node.connect_to_peer(peer_host, peer_port)  # เรียกใช้ฟังก์ชัน connect_to_peer เพื่อเชื่อมต่อกับ peer ที่ระบุ
        elif choice == '2': #หากเลือก 2
            recipient = input("Enter recipient wallet address: ") # รับข้อมูลที่อยู่กระเป๋าเงินผู้รับ
            amount = float(input("Enter amount: ")) # รับข้อมูลจำนวนเงินและแปลงเป็นจำนวนทศนิยม
            node.create_transaction(recipient, amount) # เรียกใช้ฟังก์ชัน create_transaction เพื่อสร้างธุรกรรมใหม่
        elif choice == '3': #หากเลือก 3 
            print("All transactions:") 
            for tx in node.transactions:
                print(tx) # แสดงรายการธุรกรรมทั้งหมด
        elif choice == '4': #หากเลือก 4
            print(f"Your wallet address is: {node.wallet_address}") # แสดงที่อยู่กระเป๋าเงินของผู้ใช้
        elif choice == '5': #หากเลือก 5
            break # ออกจากโปรแกรม
        else:
            print("Invalid choice. Please try again.") # หากผู้ใช้ป้อนค่าที่ไม่ถูกต้อง แสดงข้อความแจ้งเตือน

    print("Exiting...") # แสดงข้อความว่ากำลังออกโปรแกรม