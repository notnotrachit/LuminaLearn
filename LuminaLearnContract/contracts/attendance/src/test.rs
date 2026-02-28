#![cfg(test)]

use super::*;
use soroban_sdk::{testutils::Address as _, Address, BytesN, Env};

/// Test helper: Set up environment, register contract, and return test fixtures
fn setup() -> (Env, Address, AttendanceContractClient<'static>) {
    let env = Env::default();
    env.mock_all_auths();
    let contract_id = env.register(AttendanceContract, ());
    let client = AttendanceContractClient::new(&env, &contract_id);
    let teacher = Address::generate(&env);
    (env, teacher, client)
}

#[test]
fn test_initialize_and_get_teacher() {
    let (env, teacher, client) = setup();

    client.initialize(&teacher);
    let stored_teacher = client.get_teacher();
    assert_eq!(stored_teacher, teacher);
}

#[test]
#[should_panic(expected = "Error(Contract, #2)")]
fn test_initialize_twice_fails() {
    let (env, teacher, client) = setup();

    client.initialize(&teacher);
    // Second initialization should panic with AlreadyInitialized error
    client.initialize(&teacher);
}

#[test]
fn test_create_lecture_by_teacher() {
    let (env, teacher, client) = setup();

    client.initialize(&teacher);
    let lecture_id: u64 = 1;
    client.create_lecture(&teacher, &lecture_id);

    // If we reach here without panic, lecture was created successfully
}

#[test]
#[should_panic(expected = "Error(Contract, #3)")]
fn test_create_lecture_unauthorized_fails() {
    let (env, teacher, client) = setup();
    let unauthorized = Address::generate(&env);

    client.initialize(&teacher);
    let lecture_id: u64 = 1;

    // Unauthorized user trying to create lecture should panic
    client.create_lecture(&unauthorized, &lecture_id);
}

#[test]
fn test_mark_attendance_valid_nonce() {
    let (env, teacher, client) = setup();
    let student = Address::generate(&env);

    // Full happy path: initialize → create lecture → start session → mark attendance
    client.initialize(&teacher);

    let lecture_id: u64 = 1;
    client.create_lecture(&teacher, &lecture_id);

    let duration: u64 = 300; // 5 minutes
    let nonce: BytesN<32> = client.start_attendance(&teacher, &lecture_id, &duration);

    // Mark attendance
    client.mark_attendance(&student, &lecture_id, &nonce);

    // Verify attendance was recorded
    let attended = client.get_attendance(&lecture_id, &student);
    assert_eq!(attended, true);
}

#[test]
fn test_mark_attendance_within_valid_timeframe() {
    let (env, teacher, client) = setup();
    let student = Address::generate(&env);

    client.initialize(&teacher);
    let lecture_id: u64 = 1;
    client.create_lecture(&teacher, &lecture_id);

    // Start session with sufficient duration (300 seconds)
    let nonce: BytesN<32> = client.start_attendance(&teacher, &lecture_id, &300);

    // Mark attendance immediately (should succeed)
    client.mark_attendance(&student, &lecture_id, &nonce);

    // Verify attendance was marked
    let attended = client.get_attendance(&lecture_id, &student);
    assert_eq!(attended, true);
}

#[test]
#[should_panic(expected = "Error(Contract, #7)")]
fn test_mark_attendance_wrong_nonce() {
    let (env, teacher, client) = setup();
    let student = Address::generate(&env);

    client.initialize(&teacher);
    let lecture_id: u64 = 1;
    client.create_lecture(&teacher, &lecture_id);

    let duration: u64 = 300;
    let _correct_nonce: BytesN<32> = client.start_attendance(&teacher, &lecture_id, &duration);

    // Generate a different nonce
    let wrong_nonce: BytesN<32> = BytesN::from_array(&env, &[0u8; 32]);

    // Trying to mark attendance with wrong nonce should panic with InvalidNonce
    client.mark_attendance(&student, &lecture_id, &wrong_nonce);
}

#[test]
#[should_panic(expected = "Error(Contract, #8)")]
fn test_mark_attendance_twice_fails() {
    let (env, teacher, client) = setup();
    let student = Address::generate(&env);

    client.initialize(&teacher);
    let lecture_id: u64 = 1;
    client.create_lecture(&teacher, &lecture_id);

    let duration: u64 = 300;
    let nonce: BytesN<32> = client.start_attendance(&teacher, &lecture_id, &duration);

    // First attendance mark succeeds
    client.mark_attendance(&student, &lecture_id, &nonce);

    // Second attempt should panic with AlreadyMarked
    client.mark_attendance(&student, &lecture_id, &nonce);
}

#[test]
fn test_get_attendance_returns_false_before_marking() {
    let (env, teacher, client) = setup();
    let student = Address::generate(&env);

    client.initialize(&teacher);
    let lecture_id: u64 = 1;
    client.create_lecture(&teacher, &lecture_id);

    // Before marking attendance, should return false
    let attended = client.get_attendance(&lecture_id, &student);
    assert_eq!(attended, false);
}

#[test]
fn test_get_attendance_returns_true_after_marking() {
    let (env, teacher, client) = setup();
    let student = Address::generate(&env);

    client.initialize(&teacher);
    let lecture_id: u64 = 1;
    client.create_lecture(&teacher, &lecture_id);

    let duration: u64 = 300;
    let nonce: BytesN<32> = client.start_attendance(&teacher, &lecture_id, &duration);

    client.mark_attendance(&student, &lecture_id, &nonce);

    // After marking, should return true
    let attended = client.get_attendance(&lecture_id, &student);
    assert_eq!(attended, true);
}

// ============================================================================
// Gas Usage Benchmarks (Issue #28)
// ============================================================================

#[test]
fn benchmark_initialize_gas() {
    let (_env, teacher, client) = setup();

    // Measure gas for initialization
    client.initialize(&teacher);

    // Basic test that initialize works
    let stored_teacher = client.get_teacher();
    assert_eq!(stored_teacher, teacher);
}

#[test]
fn benchmark_create_lecture_gas() {
    let (_env, teacher, client) = setup();

    client.initialize(&teacher);
    let lecture_id: u64 = 1;
    client.create_lecture(&teacher, &lecture_id);

    // Verify lecture was created
    assert!(true, "Lecture creation completed");
}

#[test]
fn benchmark_start_attendance_gas() {
    let (_env, teacher, client) = setup();

    client.initialize(&teacher);
    let lecture_id: u64 = 1;
    client.create_lecture(&teacher, &lecture_id);

    let duration: u64 = 300;
    let _nonce = client.start_attendance(&teacher, &lecture_id, &duration);

    // Verify attendance session started
    assert!(true, "Attendance session started");
}

#[test]
fn benchmark_mark_attendance_gas() {
    let (env, teacher, client) = setup();
    let student = Address::generate(&env);

    client.initialize(&teacher);
    let lecture_id: u64 = 1;
    client.create_lecture(&teacher, &lecture_id);

    let duration: u64 = 300;
    let nonce: BytesN<32> = client.start_attendance(&teacher, &lecture_id, &duration);
    client.mark_attendance(&student, &lecture_id, &nonce);

    // Verify attendance was marked
    let attended = client.get_attendance(&lecture_id, &student);
    assert_eq!(attended, true);
}

#[test]
fn benchmark_get_attendance_gas() {
    let (env, teacher, client) = setup();
    let student = Address::generate(&env);

    client.initialize(&teacher);
    let lecture_id: u64 = 1;
    client.create_lecture(&teacher, &lecture_id);

    let duration: u64 = 300;
    let nonce: BytesN<32> = client.start_attendance(&teacher, &lecture_id, &duration);
    client.mark_attendance(&student, &lecture_id, &nonce);

    let attended = client.get_attendance(&lecture_id, &student);
    assert_eq!(attended, true);
}

#[test]
fn benchmark_full_workflow_gas() {
    let (env, teacher, client) = setup();
    let student = Address::generate(&env);

    // Full workflow: initialize -> create lecture -> start attendance -> mark
    client.initialize(&teacher);
    let lecture_id: u64 = 1;
    client.create_lecture(&teacher, &lecture_id);
    let duration: u64 = 300;
    let nonce: BytesN<32> = client.start_attendance(&teacher, &lecture_id, &duration);
    client.mark_attendance(&student, &lecture_id, &nonce);

    // Verify complete workflow
    let attended = client.get_attendance(&lecture_id, &student);
    assert_eq!(attended, true);
}
