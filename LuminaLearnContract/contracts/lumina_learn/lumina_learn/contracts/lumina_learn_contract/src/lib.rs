#![no_std]
use soroban_sdk::{contract, contractimpl, contracttype, symbol_short, vec, Env, String, Symbol, Vec, Address, Map, Option, IntoVal, Val};

// --- Data Structures ---
#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Teacher {
    pub id: Address,
    // Add other teacher details if needed
}

#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Student {
    pub id: Address,
    pub enrolled_courses: Vec<Symbol>,
}

#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Course {
    pub id: Symbol,
    pub teacher: Address,
    pub name: String,
    pub description: String,
    pub price: u128, // Price in stroops (smallest unit of XLM)
    // assignments and enrolled_students are managed via separate keys for scalability
}

#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Assignment {
    pub id: Symbol,
    pub course_id: Symbol,
    pub title: String,
    pub description: String,
}

#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Grade {
    pub score: u32, // e.g., percentage 0-100
    pub feedback: String,
}

#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Submission {
    pub student_id: Address,
    pub assignment_id: Symbol,
    pub course_id: Symbol, // Added for easier lookup
    pub content: String,
    pub grade: Option<Grade>,
}

// --- Attendance Specific Structures ---
#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Lecture {
    pub id: Symbol,
    pub course_id: Symbol,
    pub title: String, 
    pub date: u64, // Unix timestamp
    pub duration: u32, // Duration in minutes
}

#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct AttendanceSession {
    pub lecture_id: Symbol,
    pub start_time: u64, // Unix timestamp
    pub end_time: u64,   // Unix timestamp
    pub is_active: bool,
    pub nonce: String,   // For QR code verification
}

#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct AttendanceRecord {
    pub student_id: Address,
    pub lecture_id: Symbol,
    pub timestamp: u64, // When attendance was recorded
    pub verified: bool, // Whether the attendance was verified (e.g., via QR code)
}

// --- Storage Keys ---
#[derive(Clone)]
#[contracttype]
pub enum DataKey {
    Teacher(Address), // Key for storing teacher status/data (using bool for existence check)
    Student(Address), // Key for storing student data (Student struct)
    Course(Symbol),   // Key for storing course data (Course struct)
    Assignment(Symbol, Symbol), // Key: (CourseID, AssignmentID) -> Assignment struct
    Submission(Symbol, Symbol, Address), // Key: (CourseID, AssignmentID, StudentID) -> Submission struct
    CourseAssignments(Symbol), // Key: CourseID -> Vec<AssignmentID>
    StudentCourses(Address), // Key: StudentID -> Vec<CourseID> (Stored within Student struct)
    CourseStudents(Symbol), // Key: CourseID -> Vec<StudentID>
    Admin, // Key for storing admin address

    // Attendance specific keys
    Lecture(Symbol), // Key: LectureID -> Lecture struct
    CourseLectures(Symbol), // Key: CourseID -> Vec<LectureID>
    AttendanceSession(Symbol), // Key: LectureID -> AttendanceSession
    AttendanceRecord(Symbol, Address), // Key: (LectureID, StudentID) -> AttendanceRecord
    LectureAttendees(Symbol), // Key: LectureID -> Vec<StudentID> of students who attended
}

// --- Contract ---
#[contract]
pub struct LuminaLearnContract;

// --- Implementation ---
#[contractimpl]
impl LuminaLearnContract {

    // --- Initialization --- (Optional: Set an admin on deploy)
    pub fn initialize(env: Env, admin: Address) {
        if env.storage().instance().has(&DataKey::Admin) {
            panic!("Contract already initialized");
        }
        env.storage().instance().set(&DataKey::Admin, &admin);
    }

    // --- Registration ---
    pub fn register_teacher(env: Env, teacher_id: Address) {
        // Optional: Add admin check if only admin can register teachers
        // let admin = env.storage().instance().get(&DataKey::Admin).unwrap();
        // admin.require_auth();

        let key = DataKey::Teacher(teacher_id.clone());
        if env.storage().instance().has(&key) {
            panic!("Teacher already registered");
        }
        // Store boolean true to indicate registration.
        env.storage().instance().set(&key, &true);
        // TODO: Emit event TeacherRegistered(teacher_id)
    }

    pub fn register_student(env: Env, student_id: Address) {
        let key = DataKey::Student(student_id.clone());
        if env.storage().instance().has(&key) {
            panic!("Student already registered");
        }
        let student_data = Student {
            id: student_id.clone(),
            enrolled_courses: vec![&env],
        };
        env.storage().instance().set(&key, &student_data);
        // TODO: Emit event StudentRegistered(student_id)
    }

    // --- Course Management ---
    pub fn create_course(env: Env, teacher_id: Address, course_id: Symbol, name: String, description: String, price: u128) {
        teacher_id.require_auth(); // Only the teacher can create their course
        let teacher_key = DataKey::Teacher(teacher_id.clone());
        // Use get instead of has to check the boolean value explicitly
        if !env.storage().instance().get(&teacher_key).unwrap_or(false) {
             panic!("Teacher not registered");
        }

        let course_key = DataKey::Course(course_id.clone());
        if env.storage().instance().has(&course_key) {
            panic!("Course ID already exists");
        }

        let course_data = Course {
            id: course_id.clone(),
            teacher: teacher_id.clone(),
            name,
            description,
            price,
            // assignments and enrolled_students vectors removed from struct
        };
        env.storage().instance().set(&course_key, &course_data);
        // Initialize empty assignment list for the course
        env.storage().instance().set(&DataKey::CourseAssignments(course_id.clone()), &vec![&env]);
        // Initialize empty student list for the course
        env.storage().instance().set(&DataKey::CourseStudents(course_id.clone()), &vec![&env]);
        // Initialize empty lectures list for the course
        env.storage().instance().set(&DataKey::CourseLectures(course_id.clone()), &vec![&env]);

        // TODO: Emit event CourseCreated(teacher_id, course_id, name)
    }

    // --- Enrollment ---
    pub fn enroll_student(env: Env, student_id: Address, course_id: Symbol) {
        student_id.require_auth(); // Student must authorize enrollment

        let student_key = DataKey::Student(student_id.clone());
        let course_key = DataKey::Course(course_id.clone());
        let course_students_key = DataKey::CourseStudents(course_id.clone());

        let mut student: Student = env.storage().instance().get(&student_key).expect("Student not registered");
        let course: Course = env.storage().instance().get(&course_key).expect("Course not found"); // Read course data for price check

        if student.enrolled_courses.contains(&course_id) {
            panic!("Student already enrolled in this course");
        }

        // --- Payment Logic Placeholder ---
        // Assumes payment is handled externally or via a separate function call
        // that verifies token transfer before allowing enrollment.
        if course.price > 0 {
             // In a real contract, verify payment occurred.
             // panic!("Payment required for this course");
        }
        // --- End Payment Logic Placeholder ---

        // Update student's enrolled courses list (within Student struct)
        student.enrolled_courses.push_back(course_id.clone());
        env.storage().instance().set(&student_key, &student);

        // Update the separate list of students for the course
        let mut student_list: Vec<Address> = env.storage().instance().get(&course_students_key).unwrap_or_else(|| vec![&env]);
        if !student_list.contains(&student_id) { // Ensure no duplicates if logic changes
             student_list.push_back(student_id.clone());
             env.storage().instance().set(&course_students_key, &student_list);
        }


        // TODO: Emit event StudentEnrolled(student_id, course_id)
    }

    // --- Assignment Management ---
    pub fn create_assignment(env: Env, teacher_id: Address, course_id: Symbol, assignment_id: Symbol, title: String, description: String) {
        teacher_id.require_auth(); // Ensure the caller is the teacher

        let course_key = DataKey::Course(course_id.clone());
        let course: Course = env.storage().instance().get(&course_key).expect("Course not found");

        // Verify the caller is the teacher of this course
        if course.teacher != teacher_id {
            panic!("Only the course teacher can add assignments");
        }

        let assignment_key = DataKey::Assignment(course_id.clone(), assignment_id.clone());
        if env.storage().instance().has(&assignment_key) {
            panic!("Assignment ID already exists for this course");
        }

        let assignment_data = Assignment {
            id: assignment_id.clone(),
            course_id: course_id.clone(),
            title,
            description,
        };
        env.storage().instance().set(&assignment_key, &assignment_data);

        // Add assignment ID to the course's assignment list
        let course_assignments_key = DataKey::CourseAssignments(course_id.clone());
        let mut assignment_list: Vec<Symbol> = env.storage().instance().get(&course_assignments_key).unwrap_or_else(|| vec![&env]);
        assignment_list.push_back(assignment_id.clone());
        env.storage().instance().set(&course_assignments_key, &assignment_list);


        // TODO: Emit event AssignmentCreated(teacher_id, course_id, assignment_id)
    }

    // --- Submission ---
    pub fn submit_assignment(env: Env, student_id: Address, course_id: Symbol, assignment_id: Symbol, content: String) {
        student_id.require_auth(); // Student must authorize submission

        let student_key = DataKey::Student(student_id.clone());
        let assignment_key = DataKey::Assignment(course_id.clone(), assignment_id.clone());
        let submission_key = DataKey::Submission(course_id.clone(), assignment_id.clone(), student_id.clone());

        // Check if student, course, and assignment exist and if student is enrolled
        let student: Student = env.storage().instance().get(&student_key).expect("Student not registered");
        if !student.enrolled_courses.contains(&course_id) {
            panic!("Student not enrolled in this course");
        }
        if !env.storage().instance().has(&assignment_key) {
            panic!("Assignment not found");
        }
        if env.storage().instance().has(&submission_key) {
             // Allow overwriting/resubmission.
             // panic!("Assignment already submitted");
        }


        let submission_data = Submission {
            student_id: student_id.clone(),
            assignment_id: assignment_id.clone(),
            course_id: course_id.clone(),
            content,
            grade: None, // Initially ungraded
        };
        env.storage().instance().set(&submission_key, &submission_data);

        // TODO: Emit event SubmissionCreated(student_id, course_id, assignment_id)
    }

    pub fn grade_submission(env: Env, teacher_id: Address, course_id: Symbol, assignment_id: Symbol, student_id: Address, score: u32, feedback: String) {
        teacher_id.require_auth(); // Teacher must authorize grading

        let course_key = DataKey::Course(course_id.clone());
        let assignment_key = DataKey::Assignment(course_id.clone(), assignment_id.clone());
        let submission_key = DataKey::Submission(course_id.clone(), assignment_id.clone(), student_id.clone());

        // Check teacher, course, and submission
        let course: Course = env.storage().instance().get(&course_key).expect("Course not found");
        if course.teacher != teacher_id {
            panic!("Only the course teacher can grade submissions");
        }
        if !env.storage().instance().has(&assignment_key) {
            panic!("Assignment not found");
        }
        
        // Get and update submission with grade
        let mut submission: Submission = env.storage().instance().get(&submission_key).expect("Submission not found");
        submission.grade = Some(Grade {
            score,
            feedback,
        });
        env.storage().instance().set(&submission_key, &submission);

        // TODO: Emit event SubmissionGraded(teacher_id, student_id, course_id, assignment_id, score)
    }

    // --- Lecture Management ---
    pub fn create_lecture(env: Env, teacher_id: Address, course_id: Symbol, lecture_id: Symbol, title: String, date: u64, duration: u32) {
        teacher_id.require_auth(); // Only the teacher can create a lecture
        
        // Verify teacher owns the course
        let course_key = DataKey::Course(course_id.clone());
        let course: Course = env.storage().instance().get(&course_key).expect("Course not found");
        if course.teacher != teacher_id {
            panic!("Only the course teacher can create lectures");
        }
        
        // Check if lecture already exists
        let lecture_key = DataKey::Lecture(lecture_id.clone());
        if env.storage().instance().has(&lecture_key) {
            panic!("Lecture ID already exists");
        }
        
        // Create lecture
        let lecture = Lecture {
            id: lecture_id.clone(),
            course_id: course_id.clone(),
            title,
            date,
            duration,
        };
        
        // Store lecture
        env.storage().instance().set(&lecture_key, &lecture);
        
        // Add lecture to course's lecture list
        let course_lectures_key = DataKey::CourseLectures(course_id.clone());
        let mut lecture_list: Vec<Symbol> = env.storage().instance().get(&course_lectures_key).unwrap_or_else(|| vec![&env]);
        lecture_list.push_back(lecture_id.clone());
        env.storage().instance().set(&course_lectures_key, &lecture_list);
        
        // Initialize empty attendees list
        env.storage().instance().set(&DataKey::LectureAttendees(lecture_id.clone()), &vec![&env]);
    }
    
    pub fn start_attendance_session(env: Env, teacher_id: Address, lecture_id: Symbol, duration_seconds: u32) {
        teacher_id.require_auth(); // Only the teacher can start an attendance session
        
        // Verify lecture exists and teacher owns the course
        let lecture_key = DataKey::Lecture(lecture_id.clone());
        let lecture: Lecture = env.storage().instance().get(&lecture_key).expect("Lecture not found");
        
        let course_key = DataKey::Course(lecture.course_id.clone());
        let course: Course = env.storage().instance().get(&course_key).expect("Course not found");
        
        if course.teacher != teacher_id {
            panic!("Only the course teacher can start attendance sessions");
        }
        
        // Check if there's already an active session
        let session_key = DataKey::AttendanceSession(lecture_id.clone());
        if env.storage().instance().has(&session_key) {
            let existing_session: AttendanceSession = env.storage().instance().get(&session_key).unwrap();
            if existing_session.is_active {
                panic!("An attendance session is already active for this lecture");
            }
        }
        
        // Generate nonce (in practice, this would be a secure random value)
        let nonce = format!("nonce_{}", env.ledger().timestamp());
        
        // Create new session
        let now = env.ledger().timestamp();
        let session = AttendanceSession {
            lecture_id: lecture_id.clone(),
            start_time: now,
            end_time: now + duration_seconds as u64,
            is_active: true,
            nonce,
        };
        
        // Store session
        env.storage().instance().set(&session_key, &session);
    }
    
    pub fn mark_attendance(env: Env, student_id: Address, lecture_id: Symbol, nonce: String) {
        student_id.require_auth(); // Student must authorize attendance marking
        
        // Verify lecture exists
        let lecture_key = DataKey::Lecture(lecture_id.clone());
        let lecture: Lecture = env.storage().instance().get(&lecture_key).expect("Lecture not found");
        
        // Verify student is enrolled in the course
        let student_key = DataKey::Student(student_id.clone());
        let student: Student = env.storage().instance().get(&student_key).expect("Student not registered");
        
        if !student.enrolled_courses.contains(&lecture.course_id) {
            panic!("Student not enrolled in this course");
        }
        
        // Check if there's an active session with matching nonce
        let session_key = DataKey::AttendanceSession(lecture_id.clone());
        if !env.storage().instance().has(&session_key) {
            panic!("No attendance session found for this lecture");
        }
        
        let session: AttendanceSession = env.storage().instance().get(&session_key).unwrap();
        if !session.is_active {
            panic!("Attendance session is not active");
        }
        
        let now = env.ledger().timestamp();
        if now > session.end_time {
            panic!("Attendance session has expired");
        }
        
        if session.nonce != nonce {
            panic!("Invalid attendance code");
        }
        
        // Check if student already marked attendance
        let record_key = DataKey::AttendanceRecord(lecture_id.clone(), student_id.clone());
        if env.storage().instance().has(&record_key) {
            panic!("Attendance already marked");
        }
        
        // Create attendance record
        let record = AttendanceRecord {
            student_id: student_id.clone(),
            lecture_id: lecture_id.clone(),
            timestamp: now,
            verified: true,
        };
        
        // Store attendance record
        env.storage().instance().set(&record_key, &record);
        
        // Add student to lecture attendees list
        let attendees_key = DataKey::LectureAttendees(lecture_id.clone());
        let mut attendees: Vec<Address> = env.storage().instance().get(&attendees_key).unwrap_or_else(|| vec![&env]);
        if !attendees.contains(&student_id) {
            attendees.push_back(student_id.clone());
            env.storage().instance().set(&attendees_key, &attendees);
        }
    }
    
    pub fn close_attendance_session(env: Env, teacher_id: Address, lecture_id: Symbol) {
        teacher_id.require_auth(); // Only the teacher can close an attendance session
        
        // Verify lecture exists and teacher owns the course
        let lecture_key = DataKey::Lecture(lecture_id.clone());
        let lecture: Lecture = env.storage().instance().get(&lecture_key).expect("Lecture not found");
        
        let course_key = DataKey::Course(lecture.course_id.clone());
        let course: Course = env.storage().instance().get(&course_key).expect("Course not found");
        
        if course.teacher != teacher_id {
            panic!("Only the course teacher can close attendance sessions");
        }
        
        // Check if there's an active session
        let session_key = DataKey::AttendanceSession(lecture_id.clone());
        if !env.storage().instance().has(&session_key) {
            panic!("No attendance session found for this lecture");
        }
        
        let mut session: AttendanceSession = env.storage().instance().get(&session_key).unwrap();
        if !session.is_active {
            panic!("Attendance session is not active");
        }
        
        // Update session
        session.is_active = false;
        
        // Store updated session
        env.storage().instance().set(&session_key, &session);
    }
    
    pub fn manual_attendance(env: Env, teacher_id: Address, lecture_id: Symbol, student_id: Address) {
        teacher_id.require_auth(); // Only the teacher can mark manual attendance
        
        // Verify lecture exists and teacher owns the course
        let lecture_key = DataKey::Lecture(lecture_id.clone());
        let lecture: Lecture = env.storage().instance().get(&lecture_key).expect("Lecture not found");
        
        let course_key = DataKey::Course(lecture.course_id.clone());
        let course: Course = env.storage().instance().get(&course_key).expect("Course not found");
        
        if course.teacher != teacher_id {
            panic!("Only the course teacher can mark manual attendance");
        }
        
        // Verify student is enrolled in the course
        let student_key = DataKey::Student(student_id.clone());
        let student: Student = env.storage().instance().get(&student_key).expect("Student not registered");
        
        if !student.enrolled_courses.contains(&lecture.course_id) {
            panic!("Student not enrolled in this course");
        }
        
        // Check if student already marked attendance
        let record_key = DataKey::AttendanceRecord(lecture_id.clone(), student_id.clone());
        if env.storage().instance().has(&record_key) {
            panic!("Attendance already marked");
        }
        
        // Create attendance record (marked as not verified since it's manual)
        let record = AttendanceRecord {
            student_id: student_id.clone(),
            lecture_id: lecture_id.clone(),
            timestamp: env.ledger().timestamp(),
            verified: false, // Manual attendance is not verified through QR code
        };
        
        // Store attendance record
        env.storage().instance().set(&record_key, &record);
        
        // Add student to lecture attendees list
        let attendees_key = DataKey::LectureAttendees(lecture_id.clone());
        let mut attendees: Vec<Address> = env.storage().instance().get(&attendees_key).unwrap_or_else(|| vec![&env]);
        if !attendees.contains(&student_id) {
            attendees.push_back(student_id.clone());
            env.storage().instance().set(&attendees_key, &attendees);
        }
    }
    
    // --- Query Functions ---
    pub fn get_course(env: Env, course_id: Symbol) -> Option<Course> {
        let key = DataKey::Course(course_id);
        env.storage().instance().get(&key)
    }
    
    pub fn get_student(env: Env, student_id: Address) -> Option<Student> {
        let key = DataKey::Student(student_id);
        env.storage().instance().get(&key)
    }
    
    pub fn get_assignment(env: Env, course_id: Symbol, assignment_id: Symbol) -> Option<Assignment> {
        let key = DataKey::Assignment(course_id, assignment_id);
        env.storage().instance().get(&key)
    }
    
    pub fn get_submission(env: Env, course_id: Symbol, assignment_id: Symbol, student_id: Address) -> Option<Submission> {
        let key = DataKey::Submission(course_id, assignment_id, student_id);
        env.storage().instance().get(&key)
    }
    
    pub fn get_course_assignments(env: Env, course_id: Symbol) -> Vec<Symbol> {
        let key = DataKey::CourseAssignments(course_id);
        env.storage().instance().get(&key).unwrap_or_else(|| vec![&env])
    }
    
    pub fn get_student_courses(env: Env, student_id: Address) -> Vec<Symbol> {
        if let Some(student) = Self::get_student(env.clone(), student_id) {
            student.enrolled_courses
        } else {
            vec![&env]
        }
    }
    
    pub fn get_course_students(env: Env, course_id: Symbol) -> Vec<Address> {
        let key = DataKey::CourseStudents(course_id);
        env.storage().instance().get(&key).unwrap_or_else(|| vec![&env])
    }
    
    pub fn is_teacher(env: Env, teacher_id: Address) -> bool {
        let key = DataKey::Teacher(teacher_id);
        env.storage().instance().get(&key).unwrap_or(false)
    }
    
    pub fn get_admin(env: Env) -> Option<Address> {
        env.storage().instance().get(&DataKey::Admin)
    }
    
    // --- Attendance Query Functions ---
    pub fn get_lecture(env: Env, lecture_id: Symbol) -> Option<Lecture> {
        let key = DataKey::Lecture(lecture_id);
        env.storage().instance().get(&key)
    }
    
    pub fn get_course_lectures(env: Env, course_id: Symbol) -> Vec<Symbol> {
        let key = DataKey::CourseLectures(course_id);
        env.storage().instance().get(&key).unwrap_or_else(|| vec![&env])
    }
    
    pub fn get_attendance_session(env: Env, lecture_id: Symbol) -> Option<AttendanceSession> {
        let key = DataKey::AttendanceSession(lecture_id);
        env.storage().instance().get(&key)
    }
    
    pub fn get_attendance_record(env: Env, lecture_id: Symbol, student_id: Address) -> Option<AttendanceRecord> {
        let key = DataKey::AttendanceRecord(lecture_id, student_id);
        env.storage().instance().get(&key)
    }
    
    pub fn get_lecture_attendees(env: Env, lecture_id: Symbol) -> Vec<Address> {
        let key = DataKey::LectureAttendees(lecture_id);
        env.storage().instance().get(&key).unwrap_or_else(|| vec![&env])
    }
    
    pub fn verify_attendance(env: Env, lecture_id: Symbol, student_id: Address) -> bool {
        let key = DataKey::AttendanceRecord(lecture_id, student_id);
        env.storage().instance().has(&key)
    }
    
    pub fn get_student_attendance_stats(env: Env, student_id: Address, course_id: Symbol) -> (u32, u32) {
        // Returns (attended_count, total_lectures) for a student in a course
        let lecture_ids = Self::get_course_lectures(env.clone(), course_id);
        let total_lectures = lecture_ids.len() as u32;
        
        let mut attended_count = 0;
        
        for lecture_id in lecture_ids.iter() {
            if Self::verify_attendance(env.clone(), lecture_id.clone(), student_id.clone()) {
                attended_count += 1;
            }
        }
        
        (attended_count, total_lectures)
    }
}

#[cfg(test)]
mod test;
