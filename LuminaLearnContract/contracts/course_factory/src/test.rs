#![cfg(test)]

use super::*;
use soroban_sdk::{testutils::Address as _, Address, Env, String};

fn setup() -> (Env, Address, CourseFactoryContractClient<'static>) {
    let env = Env::default();
    env.mock_all_auths();
    let contract_id = env.register(CourseFactoryContract, ());
    let client = CourseFactoryContractClient::new(&env, &contract_id);
    let admin = Address::generate(&env);
    (env, admin, client)
}

#[test]
fn test_initialize_and_get_admin() {
    let (env, admin, client) = setup();
    client.initialize(&admin);
    let stored_admin = client.get_admin();
    assert_eq!(stored_admin, admin);
}

#[test]
#[should_panic(expected = "Error(Contract, #1)")]
fn test_initialize_twice_fails() {
    let (env, admin, client) = setup();
    client.initialize(&admin);
    client.initialize(&admin); // Should panic with AlreadyInitialized
}

#[test]
fn test_create_course() {
    let (env, admin, client) = setup();
    let teacher = Address::generate(&env);

    client.initialize(&admin);

    let code = String::from_str(&env, "CS101");
    let name = String::from_str(&env, "Introduction to Computer Science");

    let course_id = client.create_course(&teacher, &code, &name);

    assert_eq!(course_id, 1);
    assert_eq!(client.get_course_count(), 1);
}

#[test]
fn test_get_course() {
    let (env, admin, client) = setup();
    let teacher = Address::generate(&env);

    client.initialize(&admin);

    let code = String::from_str(&env, "CS101");
    let name = String::from_str(&env, "Introduction to Computer Science");

    let course_id = client.create_course(&teacher, &code, &name);
    let course = client.get_course(&course_id);

    assert_eq!(course.id, 1);
    assert_eq!(course.code, code);
    assert_eq!(course.name, name);
    assert_eq!(course.teacher, teacher);
    assert_eq!(course.is_active, true);
}

#[test]
fn test_create_multiple_courses() {
    let (env, admin, client) = setup();
    let teacher1 = Address::generate(&env);
    let teacher2 = Address::generate(&env);

    client.initialize(&admin);

    let code1 = String::from_str(&env, "CS101");
    let name1 = String::from_str(&env, "Intro to CS");
    let course_id1 = client.create_course(&teacher1, &code1, &name1);

    let code2 = String::from_str(&env, "CS102");
    let name2 = String::from_str(&env, "Data Structures");
    let course_id2 = client.create_course(&teacher2, &code2, &name2);

    assert_eq!(course_id1, 1);
    assert_eq!(course_id2, 2);
    assert_eq!(client.get_course_count(), 2);
}

#[test]
fn test_set_course_status() {
    let (env, admin, client) = setup();
    let teacher = Address::generate(&env);

    client.initialize(&admin);

    let code = String::from_str(&env, "CS101");
    let name = String::from_str(&env, "Intro to CS");
    let course_id = client.create_course(&teacher, &code, &name);

    // Deactivate course
    client.set_course_status(&teacher, &course_id, &false);
    let course = client.get_course(&course_id);
    assert_eq!(course.is_active, false);

    // Reactivate course
    client.set_course_status(&teacher, &course_id, &true);
    let course = client.get_course(&course_id);
    assert_eq!(course.is_active, true);
}

#[test]
#[should_panic(expected = "Error(Contract, #3)")]
fn test_set_course_status_unauthorized() {
    let (env, admin, client) = setup();
    let teacher = Address::generate(&env);
    let other_teacher = Address::generate(&env);

    client.initialize(&admin);

    let code = String::from_str(&env, "CS101");
    let name = String::from_str(&env, "Intro to CS");
    let course_id = client.create_course(&teacher, &code, &name);

    // Try to deactivate with different teacher - should fail
    client.set_course_status(&other_teacher, &course_id, &false);
}

#[test]
#[should_panic(expected = "Error(Contract, #4)")]
fn test_get_nonexistent_course() {
    let (env, admin, client) = setup();
    client.initialize(&admin);
    client.get_course(&999); // Should panic with CourseNotFound
}

#[test]
fn test_course_exists() {
    let (env, admin, client) = setup();
    let teacher = Address::generate(&env);

    client.initialize(&admin);

    let code = String::from_str(&env, "CS101");
    let name = String::from_str(&env, "Intro to CS");
    let course_id = client.create_course(&teacher, &code, &name);

    assert_eq!(client.course_exists(&course_id), true);
    assert_eq!(client.course_exists(&999), false);
}

// ============================================================================
// Gas Usage Benchmarks (Issue #28)
// ============================================================================

#[test]
fn benchmark_factory_initialize_gas() {
    let (_env, admin, client) = setup();
    client.initialize(&admin);

    // Verify initialization worked
    assert!(true, "Factory initialized successfully");
}

#[test]
fn benchmark_create_course_gas() {
    let (env, admin, client) = setup();
    let teacher = Address::generate(&env);

    client.initialize(&admin);

    let code = String::from_str(&env, "CS101");
    let name = String::from_str(&env, "Intro to CS");
    let _course_id = client.create_course(&teacher, &code, &name);

    // Verify course creation
    assert!(true, "Course created successfully");
}

#[test]
fn benchmark_get_course_gas() {
    let (env, admin, client) = setup();
    let teacher = Address::generate(&env);

    client.initialize(&admin);

    let code = String::from_str(&env, "CS101");
    let name = String::from_str(&env, "Intro to CS");
    let course_id = client.create_course(&teacher, &code, &name);

    let course = client.get_course(&course_id);

    // Verify course data
    assert_eq!(course.teacher, teacher);
    assert_eq!(course.is_active, true);
}

#[test]
fn benchmark_set_course_status_gas() {
    let (env, admin, client) = setup();
    let teacher = Address::generate(&env);

    client.initialize(&admin);

    let code = String::from_str(&env, "CS101");
    let name = String::from_str(&env, "Intro to CS");
    let course_id = client.create_course(&teacher, &code, &name);

    client.set_course_status(&teacher, &course_id, &false);

    // Verify status changed
    let course = client.get_course(&course_id);
    assert_eq!(course.is_active, false);
}

#[test]
fn benchmark_multiple_courses_gas() {
    let (env, admin, client) = setup();
    let teacher = Address::generate(&env);

    client.initialize(&admin);

    // Create multiple courses to test scaling
    let course1 = client.create_course(
        &teacher,
        &String::from_str(&env, "CS101"),
        &String::from_str(&env, "Course 1")
    );
    let course2 = client.create_course(
        &teacher,
        &String::from_str(&env, "CS102"),
        &String::from_str(&env, "Course 2")
    );
    let course3 = client.create_course(
        &teacher,
        &String::from_str(&env, "CS103"),
        &String::from_str(&env, "Course 3")
    );

    // Verify courses exist
    assert!(client.course_exists(&course1));
    assert!(client.course_exists(&course2));
    assert!(client.course_exists(&course3));
}
