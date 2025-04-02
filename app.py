from flask import Flask, render_template, request, redirect, flash, session
import os
from model import collect_training_data, mark_attendance, train_model, get_all_students, update_student, delete_student
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "1️b7d9f3c8e1a24d65f89e3b7f6c1d2a9e0f4c5b8a6d3e7f9a1b2c3d4e5f6a7b8"  # Cần có secret_key để sử dụng flash message

# Kết nối MongoDB
client = MongoClient("mongodb+srv://anhphuongphanqw:hgsBGUo5iBhsGJHT@cluster0.t4qnspy.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
db = client["attendance_system"]
teachers_collection = db["teachers"]
subjects_collection = db["subjects"]
attendances_collection = db["attendances"]

# Trang chủ
@app.route('/')
def home():
    return render_template('index.html')

# Trang đăng nhập
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Kiểm tra tên đăng nhập và mật khẩu
        teacher = teachers_collection.find_one({"username": username})
        if teacher and check_password_hash(teacher["password"], password):
            # Lưu thông tin giáo viên vào session
            session['teacher_username'] = teacher['username']
            session['subjects'] = teacher['subjects']  # Lưu các môn học mà giáo viên phụ trách
            flash("Đăng nhập thành công!", "success")
            return redirect('/mark_attendance')  # Chuyển đến trang điểm danh
        else:
            flash("Tên đăng nhập hoặc mật khẩu không đúng.", "danger")
            return redirect('/login')

    return render_template('login.html')

# Trang đăng ký khuôn mặt sinh viên
@app.route('/register', methods=['POST'])
def register():
    student_name = request.form['student_name']
    if student_name:
        # Thu thập dữ liệu khuôn mặt và huấn luyện mô hình
        collect_training_data(student_name) 
        train_model()  # Gọi hàm để huấn luyện mô hình nhận diện khuôn mặt
        flash(f"Đã đăng ký khuôn mặt thành công cho sinh viên {student_name}.", "success")
    else:
        flash("Vui lòng nhập tên sinh viên!", "danger")
    
    return redirect('/')

# Trang điểm danh
@app.route('/mark_attendance', methods=['GET', 'POST'])
def mark_attendance_web():
    if 'teacher_username' not in session:
        flash("Vui lòng đăng nhập!", "danger")
        return redirect('/login')
    
    teacher_username = session['teacher_username']
    subjects = session['subjects']  # Lấy các môn học giáo viên phụ trách

    if request.method == 'POST':
        subject_name = request.form.get('subject_name')  # Lấy môn học từ form

        if subject_name in subjects:
            mark_attendance(subject_name, teacher_username)  # Gọi hàm điểm danh
            flash(f"Điểm danh môn {subject_name} thành công!", "success")
        else:
            flash("Bạn không có quyền điểm danh cho môn học này.", "danger")

    return render_template('mark_attendance.html', subjects=subjects)

# Lịch sử điểm danh
@app.route('/attendance_history', methods=['GET'])
def attendance_history():
    if 'teacher_username' not in session:
        flash("Vui lòng đăng nhập!", "danger")
        return redirect('/login')
    
    teacher_username = session['teacher_username']
    # Truy vấn lịch sử điểm danh của giáo viên
    attendance_records = attendances_collection.find({"teacher": teacher_username})

    # Chuyển kết quả truy vấn thành danh sách để dễ dàng hiển thị
    records = list(attendance_records)

    return render_template('attendance_history.html', records=records)

# Thêm môn học
@app.route('/add_subject', methods=['GET', 'POST'])
def add_subject():
    if request.method == 'POST':
        subject_name = request.form['subject_name']
        if subject_name:
            # Thêm môn học vào MongoDB
            subjects_collection.insert_one({"name": subject_name})
            flash(f"Môn học {subject_name} đã được thêm vào cơ sở dữ liệu.", "success")
        else:
            flash("Vui lòng nhập tên môn học.", "danger")
        return redirect('/add_subject')
    
    return render_template('add_subject.html')

# Thêm giáo viên
@app.route('/addteacher', methods=['GET', 'POST'])
def add_teacher():
    if request.method == 'POST':
        teacher_username = request.form['teacher_username']
        teacher_password = request.form['teacher_password']
        subjects = request.form.getlist('subjects')  # Lấy danh sách các môn học

        if teacher_username and teacher_password and subjects:
            # Mã hóa mật khẩu
            hashed_password = generate_password_hash(teacher_password)
            
            teacher = {
                "username": teacher_username,
                "password": hashed_password,
                "subjects": subjects  # Môn học mà giáo viên phụ trách
            }
            teachers_collection.insert_one(teacher)
            flash(f"Tài khoản giáo viên {teacher_username} đã được tạo.", "success")
        else:
            flash("Vui lòng nhập đầy đủ thông tin giáo viên và môn học.", "danger")
        
        return redirect('/addteacher')
    
    # Trả về trang thêm giáo viên
    subjects = [subject['name'] for subject in subjects_collection.find()]  # Lấy danh sách môn học từ MongoDB
    return render_template('teacher.html', subjects=subjects)

@app.route('/students')
def students():
    students_list = get_all_students()  # Lấy danh sách sinh viên từ MongoDB
    return render_template('students.html', students=students_list)

# Route sửa tên sinh viên
@app.route('/update_student/<student_name>/<student_id>', methods=['GET', 'POST'])
def update_student_web(student_name, student_id):
    if request.method == 'POST':
        new_name = request.form['new_name']
        if new_name:
            update_student(student_name, student_id, new_name)  # Gọi hàm sửa sinh viên
            flash(f"Sinh viên {student_name} đã được sửa thành {new_name}.", "success")
        else:
            flash("Vui lòng nhập tên mới cho sinh viên.", "danger")
        return redirect('/students')
    
    return render_template('update_student.html', student_name=student_name, student_id=student_id)

# Route xóa sinh viên
@app.route('/delete_student/<student_name>/<int:student_id>', methods=['GET', 'POST'])
def delete_student_web(student_name, student_id):
    if request.method == 'POST':
        delete_student(student_name, student_id)  # Gọi hàm xóa sinh viên
        flash(f"Sinh viên {student_name} với ID {student_id} đã được xóa.", "success")
        return redirect('/students')
    
    return render_template('delete_student.html', student_name=student_name, student_id=student_id)



if __name__ == "__main__":
    app.run(debug=True)
