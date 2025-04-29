#![cfg(test)]

extern crate std; // Required for panic messages in tests

use super::*; // Import items from lib.rs
use soroban_sdk::{
    testutils::{Address as _, Events}, // Import Address trait for random()
    vec, Env, String, Symbol, Address, IntoVal, Val, Map, BytesN,
};

// Helper function to register the contract and get a client
fn setup_test<'a>() -> (Env, LuminaLearnContractClient<'a>, Address, Address, Address) {
    let env = Env::default();
    env.mock_all_auths(); // Automatically authorize all calls in tests

    let contract_id = env.register_contract(None, LuminaLearnContract);
    let client = LuminaLearnContractClient::new(&env, &contract_id);

    // Create mock identities
    let admin = Address::random(&env);
    let teacher = Address::random(&env);
    let student = Address::random(&env);

    (env, client, admin, teacher, student)
}

#[test]
fn test_initialize_and_get_admin() {
    let (env, client, admin, _, _) = setup_test();
    client.initialize(&admin);
    assert_eq!(client.get_admin(), Some(admin));
}

#[test]
#[should_panic(expected = "Contract already initialized")]
fn test_initialize_twice() {
    let (env, client, admin, _, _) = setup_test();
    client.initialize(&admin);
    client.initialize(&admin); // Should panic
}

#[test]
fn test_register_teacher_and_check() {
    let (env, client, admin, teacher, _) = setup_test();
    client.initialize(&admin); // Initialize first
    client.register_teacher(&teacher);
    assert!(client.is_teacher(&teacher));
    assert!(!client.is_teacher(&Address::random(&env))); // Check unregistered address
}

#[test]
#[should_panic(expected = "Teacher already registered")]
fn test_register_teacher_twice() {
    let (env, client, admin, teacher, _) = setup_test();
    client.initialize(&admin);
    client.register_teacher(&teacher);
    client.register_teacher(&teacher); // Should panic
}

#[test]
fn test_register_student_and_get() {
    let (env, client, admin, _, student) = setup_test();
    client.initialize(&admin);
    client.register_student(&student);

    let student_data = client.get_student(&student).expect("Student should be registered");
    assert_eq!(student_data.id, student);
    assert_eq!(student_data.enrolled_courses.len(), 0); // Initially no courses
}

#[test]
#[should_panic(expected = "Student already registered")]
fn test_register_student_twice() {
    let (env, client, admin, _, student) = setup_test();
    client.initialize(&admin);
    client.register_student(&student);
    client.register_student(&student); // Should panic
}

#[test]
fn test_create_course() {
    let (env, client, admin, teacher, _) = setup_test();
    client.initialize(&admin);
    client.register_teacher(&teacher);

    let course_id = symbol_short!("RUST101");
    let name = String::from_str(&env, "Intro to Rust");
    let desc = String::from_str(&env, "Learn the basics");
    let price = 100_0000000; // 100 XLM in stroops

    client.create_course(&teacher, &course_id, &name, &desc, &price);

    let course_data = client.get_course(&course_id).expect("Course should exist");
    assert_eq!(course_data.id, course_id);
    assert_eq!(course_data.teacher, teacher);
    assert_eq!(course_data.name, name);
    assert_eq!(course_data.description, desc);
    assert_eq!(course_data.price, price);
    assert_eq!(client.get_course_assignments(&course_id).len(), 0); // No assignments yet
    assert_eq!(client.get_course_students(&course_id).len(), 0); // No students yet
}

#[test]
#[should_panic(expected = "Teacher not registered")]
fn test_create_course_unregistered_teacher() {
    let (env, client, admin, teacher, _) = setup_test();
    client.initialize(&admin);
    // Teacher not registered
    let course_id = symbol_short!("RUST101");
    client.create_course(
        &teacher,
        &course_id,
        &String::from_str(&env, "Intro"),
        &String::from_str(&env, "Desc"),
        &0,
    );
}

#[test]
#[should_panic(expected = "Course ID already exists")]
fn test_create_course_duplicate_id() {
    let (env, client, admin, teacher, _) = setup_test();
    client.initialize(&admin);
    client.register_teacher(&teacher);
    let course_id = symbol_short!("RUST101");
    client.create_course(
        &teacher,
        &course_id,
        &String::from_str(&env, "Intro"),
        &String::from_str(&env, "Desc"),
        &0,
    );
    // Create again with same ID
    client.create_course(
        &teacher,
        &course_id,
        &String::from_str(&env, "Intro V2"),
        &String::from_str(&env, "Desc V2"),
        &0,
    );
}

#[test]
fn test_enroll_student() {
    let (env, client, admin, teacher, student) = setup_test();
    client.initialize(&admin);
    client.register_teacher(&teacher);
    client.register_student(&student);

    let course_id = symbol_short!("RUST101");
    client.create_course(
        &teacher,
        &course_id,
        &String::from_str(&env, "Intro"),
        &String::from_str(&env, "Desc"),
        &0, // Free course for simplicity
    );

    client.enroll_student(&student, &course_id);

    // Check student data
    let student_data = client.get_student(&student).unwrap();
    assert_eq!(student_data.enrolled_courses.len(), 1);
    assert!(student_data.enrolled_courses.contains(&course_id));

    // Check course data
    let course_students = client.get_course_students(&course_id);
    assert_eq!(course_students.len(), 1);
    assert!(course_students.contains(&student));
}

#[test]
#[should_panic(expected = "Student not registered")]
fn test_enroll_unregistered_student() {
    let (env, client, admin, teacher, student) = setup_test();
    // student is not registered
    client.initialize(&admin);
    client.register_teacher(&teacher);
    let course_id = symbol_short!("RUST101");
    client.create_course(&teacher, &course_id, &String::from_str(&env, "Intro"), &String::from_str(&env, "Desc"), &0);

    client.enroll_student(&student, &course_id); // Should panic
}

#[test]
#[should_panic(expected = "Course not found")]
fn test_enroll_nonexistent_course() {
    let (env, client, admin, _, student) = setup_test();
    client.initialize(&admin);
    client.register_student(&student);
    let course_id = symbol_short!("NOSUCH");

    client.enroll_student(&student, &course_id); // Should panic
}

#[test]
#[should_panic(expected = "Student already enrolled in this course")]
fn test_enroll_student_twice() {
    let (env, client, admin, teacher, student) = setup_test();
    client.initialize(&admin);
    client.register_teacher(&teacher);
    client.register_student(&student);
    let course_id = symbol_short!("RUST101");
    client.create_course(&teacher, &course_id, &String::from_str(&env, "Intro"), &String::from_str(&env, "Desc"), &0);

    client.enroll_student(&student, &course_id);
    client.enroll_student(&student, &course_id); // Should panic
}


#[test]
fn test_create_assignment() {
    let (env, client, admin, teacher, _) = setup_test();
    client.initialize(&admin);
    client.register_teacher(&teacher);
    let course_id = symbol_short!("RUST101");
    client.create_course(&teacher, &course_id, &String::from_str(&env, "Intro"), &String::from_str(&env, "Desc"), &0);

    let assignment_id = symbol_short!("ASG1");
    let title = String::from_str(&env, "First Assignment");
    let desc = String::from_str(&env, "Write hello world");

    client.create_assignment(&teacher, &course_id, &assignment_id, &title, &desc);

    let assignment_data = client.get_assignment(&course_id, &assignment_id).expect("Assignment should exist");
    assert_eq!(assignment_data.id, assignment_id);
    assert_eq!(assignment_data.course_id, course_id);
    assert_eq!(assignment_data.title, title);
    assert_eq!(assignment_data.description, desc);

    // Check course assignment list
    let assignments = client.get_course_assignments(&course_id);
    assert_eq!(assignments.len(), 1);
    assert!(assignments.contains(&assignment_id));
}

#[test]
#[should_panic(expected = "Only the course teacher can add assignments")]
fn test_create_assignment_not_teacher() {
    let (env, client, admin, teacher, student) = setup_test(); // Use student as wrong caller
    client.initialize(&admin);
    client.register_teacher(&teacher);
    let course_id = symbol_short!("RUST101");
    client.create_course(&teacher, &course_id, &String::from_str(&env, "Intro"), &String::from_str(&env, "Desc"), &0);

    let assignment_id = symbol_short!("ASG1");
    client.create_assignment(
        &student, // Wrong caller
        &course_id,
        &assignment_id,
        &String::from_str(&env, "Title"),
        &String::from_str(&env, "Desc"),
    );
}

#[test]
fn test_submit_assignment() {
    let (env, client, admin, teacher, student) = setup_test();
    client.initialize(&admin);
    client.register_teacher(&teacher);
    client.register_student(&student);
    let course_id = symbol_short!("RUST101");
    client.create_course(&teacher, &course_id, &String::from_str(&env, "Intro"), &String::from_str(&env, "Desc"), &0);
    client.enroll_student(&student, &course_id);
    let assignment_id = symbol_short!("ASG1");
    client.create_assignment(&teacher, &course_id, &assignment_id, &String::from_str(&env, "Title"), &String::from_str(&env, "Desc"));

    let content = String::from_str(&env, "My submission content");
    client.submit_assignment(&student, &course_id, &assignment_id, &content);

    let submission_data = client.get_submission(&course_id, &assignment_id, &student).expect("Submission should exist");
    assert_eq!(submission_data.student_id, student);
    assert_eq!(submission_data.assignment_id, assignment_id);
    assert_eq!(submission_data.course_id, course_id);
    assert_eq!(submission_data.content, content);
    assert!(submission_data.grade.is_none()); // Not graded yet
}

#[test]
#[should_panic(expected = "Student not enrolled in this course")]
fn test_submit_assignment_not_enrolled() {
    let (env, client, admin, teacher, student) = setup_test();
    client.initialize(&admin);
    client.register_teacher(&teacher);
    client.register_student(&student); // Student registered but not enrolled
    let course_id = symbol_short!("RUST101");
    client.create_course(&teacher, &course_id, &String::from_str(&env, "Intro"), &String::from_str(&env, "Desc"), &0);
    let assignment_id = symbol_short!("ASG1");
    client.create_assignment(&teacher, &course_id, &assignment_id, &String::from_str(&env, "Title"), &String::from_str(&env, "Desc"));

    client.submit_assignment(
        &student,
        &course_id,
        &assignment_id,
        &String::from_str(&env, "Content"),
    ); // Should panic
}

#[test]
fn test_grade_submission() {
    let (env, client, admin, teacher, student) = setup_test();
    client.initialize(&admin);
    client.register_teacher(&teacher);
    client.register_student(&student);
    let course_id = symbol_short!("RUST101");
    client.create_course(&teacher, &course_id, &String::from_str(&env, "Intro"), &String::from_str(&env, "Desc"), &0);
    client.enroll_student(&student, &course_id);
    let assignment_id = symbol_short!("ASG1");
    client.create_assignment(&teacher, &course_id, &assignment_id, &String::from_str(&env, "Title"), &String::from_str(&env, "Desc"));
    client.submit_assignment(&student, &course_id, &assignment_id, &String::from_str(&env, "Content"));

    let score = 95u32;
    let feedback = String::from_str(&env, "Good job!");
    client.grade_submission(&teacher, &course_id, &assignment_id, &student, &score, &feedback);

    let submission_data = client.get_submission(&course_id, &assignment_id, &student).unwrap();
    let grade = submission_data.grade.expect("Should be graded");
    assert_eq!(grade.score, score);
    assert_eq!(grade.feedback, feedback);
}

#[test]
#[should_panic(expected = "Only the course teacher can grade submissions")]
fn test_grade_submission_not_teacher() {
    let (env, client, admin, teacher, student) = setup_test();
    let other_teacher = Address::random(&env); // Another teacher tries to grade
    client.initialize(&admin);
    client.register_teacher(&teacher);
    client.register_teacher(&other_teacher);
    client.register_student(&student);
    let course_id = symbol_short!("RUST101");
    client.create_course(&teacher, &course_id, &String::from_str(&env, "Intro"), &String::from_str(&env, "Desc"), &0);
    client.enroll_student(&student, &course_id);
    let assignment_id = symbol_short!("ASG1");
    client.create_assignment(&teacher, &course_id, &assignment_id, &String::from_str(&env, "Title"), &String::from_str(&env, "Desc"));
    client.submit_assignment(&student, &course_id, &assignment_id, &String::from_str(&env, "Content"));

    client.grade_submission(
        &other_teacher, // Wrong teacher
        &course_id,
        &assignment_id,
        &student,
        &90,
        &String::from_str(&env, "Feedback"),
    ); // Should panic
}

#[test]
#[should_panic(expected = "Submission not found")]
fn test_grade_nonexistent_submission() {
    let (env, client, admin, teacher, student) = setup_test();
    client.initialize(&admin);
    client.register_teacher(&teacher);
    let course_id = symbol_short!("RUST101");
    client.create_course(&teacher, &course_id, &String::from_str(&env, "Intro"), &String::from_str(&env, "Desc"), &0);
    let assignment_id = symbol_short!("ASG1");
    client.create_assignment(&teacher, &course_id, &assignment_id, &String::from_str(&env, "Title"), &String::from_str(&env, "Desc"));
    // No submission made

    client.grade_submission(
        &teacher,
        &course_id,
        &assignment_id,
        &student, // Student didn't submit
        &90,
        &String::from_str(&env, "Feedback"),
    ); // Should panic
}

#[test]
fn test_get_student_courses() {
     let (env, client, admin, teacher, student) = setup_test();
     client.initialize(&admin);
     client.register_teacher(&teacher);
     client.register_student(&student);

     let course1_id = symbol_short!("CRS1");
     let course2_id = symbol_short!("CRS2");
     client.create_course(&teacher, &course1_id, &String::from_str(&env, "C1"), &String::from_str(&env, "D1"), &0);
     client.create_course(&teacher, &course2_id, &String::from_str(&env, "C2"), &String::from_str(&env, "D2"), &0);

     client.enroll_student(&student, &course1_id);
     client.enroll_student(&student, &course2_id);

     let enrolled = client.get_student_courses(&student);
     assert_eq!(enrolled.len(), 2);
     assert!(enrolled.contains(&course1_id));
     assert!(enrolled.contains(&course2_id));

     // Check for non-registered student
     let other_student = Address::random(&env);
     let other_enrolled = client.get_student_courses(&other_student);
     assert_eq!(other_enrolled.len(), 0);
}
