import cv2
import dlib
import os
import pickle
import numpy as np
from datetime import datetime
from pymongo import MongoClient
import bcrypt
import shutil


client = MongoClient("mongodb+srv://anhphuongphanqw:hgsBGUo5iBhsGJHT@cluster0.t4qnspy.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
db = client["attendance_system"]

# Tạo các collection (bảng) cho giáo viên, môn học và điểm danh
teachers_collection = db["teachers"]
subjects_collection = db["subjects"]
attendances_collection = db["attendances"]
students_collection = db["students"]

# Mô hình tài khoản giáo viên
def create_teacher_account(username, password):
    # Mã hóa mật khẩu
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    teacher = {
        "username": username,
        "password": hashed_password,
        "subjects": []  # Danh sách môn học mà giáo viên phụ trách
    }
    teachers_collection.insert_one(teacher)
    print(f"Tài khoản giáo viên {username} đã được tạo.")

# Mô hình môn học
def create_subject(subject_name):
    subject = {
        "name": subject_name
    }
    subjects_collection.insert_one(subject)
    print(f"Môn học {subject_name} đã được tạo.")

# Gán môn học cho giáo viên
def assign_subject_to_teacher(teacher_username, subject_name):
    teacher = teachers_collection.find_one({"username": teacher_username})
    if teacher:
        subjects_collection.update_one(
            {"name": subject_name},
            {"$addToSet": {"subjects": subject_name}}
        )
        teachers_collection.update_one(
            {"username": teacher_username},
            {"$addToSet": {"subjects": subject_name}}
        )
        print(f"Môn học {subject_name} đã được gán cho giáo viên {teacher_username}.")
    else:
        print("Giáo viên không tồn tại.")

# Mô hình điểm danh
def mark_attendance_teacher(subject_name, teacher_username):
    teacher = teachers_collection.find_one({"username": teacher_username})
    if teacher and subject_name in teacher['subjects']:
        # Giả sử bạn đã có danh sách sinh viên và thời gian điểm danh
        attendance = {
            "teacher": teacher_username,
            "subject": subject_name,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "students": ["student_id_1", "student_id_2"],  # Danh sách sinh viên điểm danh
        }
        attendances_collection.insert_one(attendance)
        print(f"Điểm danh môn {subject_name} đã được lưu vào cơ sở dữ liệu.")
    else:
        print("Giáo viên không có quyền điểm danh cho môn này.")


# Khởi tạo bộ nhận diện khuôn mặt của dlib
detector = dlib.get_frontal_face_detector()
shape_predictor = dlib.shape_predictor("shape_predictor_68_face_landmarks.dat")
face_rec_model = dlib.face_recognition_model_v1("dlib_face_recognition_resnet_model_v1.dat")

def get_face_encoding(image, face):
    shape = shape_predictor(image, face)
    return np.array(face_rec_model.compute_face_descriptor(image, shape))

def generate_student_id():
    # Kiểm tra tệp 'student_ids.txt' để lấy mã ID tiếp theo
    student_ids_file = "student_ids.txt"
    
    # Nếu tệp không tồn tại, tạo tệp và gán mã sinh viên đầu tiên là 1
    if not os.path.exists(student_ids_file):
        with open(student_ids_file, "w") as f:
            f.write("1")  # Mã sinh viên bắt đầu từ 1
        return 1
    
    # Nếu tệp đã tồn tại, đọc mã ID hiện tại và tăng lên 1
    with open(student_ids_file, "r") as f:
        last_id = int(f.read().strip())
    
    # Tăng mã sinh viên và lưu lại tệp
    new_id = last_id + 1
    with open(student_ids_file, "w") as f:
        f.write(str(new_id))
    
    return new_id

def collect_training_data(student_name):
    # Mã sinh viên tự động (hoặc có thể tự động cấp mã từ hệ thống)
    student_id = generate_student_id()
    
    cap = cv2.VideoCapture(0)
    face_images = []
    face_labels = []
    os.makedirs(f"data/{student_name}_{student_id}", exist_ok=True)
    
    max_images = 50
    print(f"Đang thu thập ảnh cho {student_name} với ID {student_id}...")

    while len(face_images) < max_images:
        ret, frame = cap.read()
        if not ret:
            break
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = detector(gray)
        
        for face in faces:
            x, y, w, h = face.left(), face.top(), face.width(), face.height()
            face_image = frame[y:y+h, x:x+w]
            face_images.append(face_image)
            face_labels.append(student_name)
            cv2.imwrite(f"data/{student_name}_{student_id}/{len(face_images)}.jpg", face_image)
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
        
        cv2.imshow("Camera", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    cap.release()
    cv2.destroyAllWindows()
    print(f"Đã thu thập {len(face_images)} ảnh cho {student_name} với ID {student_id}.")
    # Lưu thông tin sinh viên vào MongoDB
    student_data = {
        "student_name": student_name,
        "student_id": student_id,
        "date_registered": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    students_collection.insert_one(student_data)  # Thêm thông tin sinh viên vào bảng students
    train_model() 
    return face_images, face_labels




def train_model():
    known_face_encodings = []
    known_face_labels = []
    known_face_ids = []  # Danh sách ID của sinh viên
    
    for student_folder in os.listdir("data"):
        student_dir = os.path.join("data", student_folder)
        if os.path.isdir(student_dir):
            # Tách tên và ID từ tên thư mục
            student_name, student_id = student_folder.rsplit("_", 1)  # Tách tên và ID
            student_id = int(student_id)  # Chuyển ID thành số nguyên
            
            for img_name in os.listdir(student_dir):
                img_path = os.path.join(student_dir, img_name)
                image = cv2.imread(img_path)
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                faces = detector(gray)
                
                for face in faces:
                    encoding = get_face_encoding(image, face)
                    known_face_encodings.append(encoding)
                    known_face_labels.append(student_name)
                    known_face_ids.append(student_id)  # Thêm ID vào danh sách
     
    # Lưu mô hình với ID sinh viên
    with open("face_model.pkl", "wb") as f:
        pickle.dump((known_face_encodings, known_face_labels, known_face_ids), f)
    print("Mô hình đã được huấn luyện và lưu thành công.")



def get_next_file_name():
    i = 1
    while True:
        filename = f"attendance{i}.txt"
        if not os.path.exists(filename):
            return filename
        i += 1

with open("face_model.pkl", "rb") as f:
    known_face_encodings, known_face_labels, known_face_ids = pickle.load(f)
# Mô hình điểm danh
# Hàm điểm danh
def mark_attendance(subject_name, teacher_username):
    teacher = teachers_collection.find_one({"username": teacher_username})
    if teacher and subject_name in teacher['subjects']:
        # Tạo danh sách sinh viên đã điểm danh
        students_attended = []

        # Đoạn mã điểm danh qua nhận diện khuôn mặt
        cap = cv2.VideoCapture(0)
        print("Đang điểm danh...")

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = detector(gray)

            for face in faces:
                encoding = get_face_encoding(frame, face)
                distances = np.linalg.norm(known_face_encodings - encoding, axis=1)
                min_distance_index = np.argmin(distances)

                name = "Unknown"
                if distances[min_distance_index] < 0.6:  # Ngưỡng độ tin cậy
                    name = known_face_labels[min_distance_index]  # Lấy tên sinh viên
                    student_id = known_face_ids[min_distance_index]  # Lấy ID sinh viên

                    # Kiểm tra xem sinh viên đã được điểm danh chưa
                    if not any(student["student_name"] == name for student in students_attended):
                        students_attended.append({
                            "student_name": name,
                            "student_id": student_id,
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        })

                    # Vẽ khung quanh khuôn mặt
                    x, y, w, h = face.left(), face.top(), face.width(), face.height()
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                    cv2.putText(frame, f"{name} - ID: {student_id}", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
            
            cv2.imshow("Camera", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
        cap.release()
        cv2.destroyAllWindows()
        
        # Lưu điểm danh vào MongoDB
        if students_attended:
            attendance = {
                "teacher": teacher_username,
                "subject": subject_name,
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "students": students_attended  # Lưu thông tin sinh viên đã điểm danh
            }
            attendances_collection.insert_one(attendance)
            print(f"Điểm danh môn {subject_name} đã được lưu vào cơ sở dữ liệu.")
        else:
            print("Không có sinh viên nào được nhận diện.")
    else:
        print("Giáo viên không có quyền điểm danh cho môn này.")

# Mô hình môn học
def create_subject(subject_name):
    subject = {
        "name": subject_name  # Tên môn học
    }
    # Thêm môn học vào MongoDB
    subjects_collection.insert_one(subject)
    print(f"Môn học {subject_name} đã được tạo và lưu vào cơ sở dữ liệu.")

from werkzeug.security import generate_password_hash

# Mô hình tài khoản giáo viên
def create_teacher_account(username, password, subjects):
    # Mã hóa mật khẩu
    hashed_password = generate_password_hash(password)

    teacher = {
        "username": username,
        "password": hashed_password,
        "subjects": subjects  # Danh sách môn học mà giáo viên phụ trách
    }
    
    # Thêm tài khoản giáo viên vào MongoDB
    teachers_collection.insert_one(teacher)
    print(f"Tài khoản giáo viên {username} đã được tạo và lưu vào cơ sở dữ liệu.")

# Gán môn học cho giáo viên
def assign_subject_to_teacher(teacher_username, subject_name):
    teacher = teachers_collection.find_one({"username": teacher_username})
    if teacher:
        subjects_collection.update_one(
            {"name": subject_name},
            {"$addToSet": {"subjects": subject_name}}
        )
        teachers_collection.update_one(
            {"username": teacher_username},
            {"$addToSet": {"subjects": subject_name}}
        )
        print(f"Môn học {subject_name} đã được gán cho giáo viên {teacher_username}.")
    else:
        print(f"Giáo viên {teacher_username} không tồn tại.")


# Hàm lấy danh sách sinh viên
def get_all_students():
    return list(students_collection.find())  # Trả về danh sách tất cả sinh viên từ MongoDB

# Hàm sửa thông tin sinh viên
def update_student(student_name, student_id, new_name):
    student = students_collection.find_one({"student_name": student_name, "student_id": student_id})
    if student:
        # Cập nhật tên sinh viên trong cơ sở dữ liệu
        students_collection.update_one(
            {"student_name": student_name, "student_id": student_id},
            {"$set": {"student_name": new_name}}
        )
        # Đổi tên thư mục chứa ảnh khuôn mặt
        old_folder = f"data/{student_name}_{student_id}"
        new_folder = f"data/{new_name}_{student_id}"
        os.rename(old_folder, new_folder)
        print(f"Tên sinh viên {student_name} đã được thay đổi thành {new_name}.")
    else:
        print(f"Sinh viên {student_name} với ID {student_id} không tồn tại.")
    train_model() 

def delete_student(student_name, student_id):
    # Xóa sinh viên khỏi MongoDB
    result = students_collection.delete_one({"student_name": student_name, "student_id": student_id})
    if result.deleted_count > 0:
        print(f"Sinh viên {student_name} với ID {student_id} đã được xóa khỏi cơ sở dữ liệu.")
    else:
        print(f"Sinh viên {student_name} không tồn tại trong cơ sở dữ liệu.")
    
    # Xóa thư mục chứa ảnh khuôn mặt của sinh viên
    student_folder = f"data/{student_name}_{student_id}"
    if os.path.exists(student_folder):
        shutil.rmtree(student_folder)
        print(f"Thư mục {student_folder} chứa ảnh khuôn mặt của sinh viên {student_name} đã được xóa.")
    else:
        print(f"Thư mục {student_folder} không tồn tại.")
    train_model() 


