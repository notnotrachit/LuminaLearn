#![no_std]

use soroban_sdk::{
    contract, contracterror, contractimpl, contracttype, panic_with_error, Address, Env, String, symbol_short,
};

// Define custom errors
#[contracterror]
#[derive(Copy, Clone, Debug, Eq, PartialEq, PartialOrd, Ord)]
#[repr(u32)]
pub enum Error {
    AlreadyInitialized = 1,
    NotInitialized = 2,
    Unauthorized = 3,
    CourseNotFound = 4,
    CourseAlreadyExists = 5,
}

#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct CourseInfo {
    pub id: u64,
    pub code: String,
    pub name: String,
    pub teacher: Address,
    pub created_at: u64,
    pub is_active: bool,
}

#[contract]
pub struct CourseFactoryContract;

#[contractimpl]
impl CourseFactoryContract {
    /// Initialize the contract with an admin
    pub fn initialize(env: Env, admin: Address) {
        if env.storage().instance().has(&symbol_short!("Admin")) {
            panic_with_error!(&env, Error::AlreadyInitialized);
        }

        admin.require_auth();
        env.storage().instance().set(&symbol_short!("Admin"), &admin);
        env.storage().instance().set(&symbol_short!("Count"), &0u64);
    }

    /// Get the admin address
    pub fn get_admin(env: Env) -> Address {
        if !env.storage().instance().has(&symbol_short!("Admin")) {
            panic_with_error!(&env, Error::NotInitialized);
        }
        env.storage()
            .instance()
            .get(&symbol_short!("Admin"))
            .unwrap()
    }

    /// Create a new course
    pub fn create_course(
        env: Env,
        teacher: Address,
        code: String,
        name: String,
    ) -> u64 {
        teacher.require_auth();

        // Get current course count
        let course_id: u64 = env
            .storage()
            .instance()
            .get(&symbol_short!("Count"))
            .unwrap_or(0);

        let new_course_id = course_id + 1;

        // Create course info
        let course = CourseInfo {
            id: new_course_id,
            code: code.clone(),
            name: name.clone(),
            teacher: teacher.clone(),
            created_at: env.ledger().timestamp(),
            is_active: true,
        };

        // Store course using composite key (course_id)
        let course_key = (symbol_short!("Course"), new_course_id);
        env.storage().instance().set(&course_key, &course);

        // Update course count
        env.storage().instance().set(&symbol_short!("Count"), &new_course_id);

        // Emit event
        env.events().publish(
            (symbol_short!("created"), teacher),
            (code, name, new_course_id),
        );

        new_course_id
    }

    /// Get course information by ID
    pub fn get_course(env: Env, course_id: u64) -> CourseInfo {
        let course_key = (symbol_short!("Course"), course_id);

        env.storage()
            .instance()
            .get(&course_key)
            .unwrap_or_else(|| panic_with_error!(&env, Error::CourseNotFound))
    }

    /// Update course status (activate/deactivate)
    pub fn set_course_status(
        env: Env,
        teacher: Address,
        course_id: u64,
        is_active: bool,
    ) {
        teacher.require_auth();

        let course_key = (symbol_short!("Course"), course_id);
        let mut course: CourseInfo = env
            .storage()
            .instance()
            .get(&course_key)
            .unwrap_or_else(|| panic_with_error!(&env, Error::CourseNotFound));

        // Verify teacher authorization
        if course.teacher != teacher {
            panic_with_error!(&env, Error::Unauthorized);
        }

        course.is_active = is_active;
        env.storage().instance().set(&course_key, &course);

        // Emit event
        env.events().publish(
            (symbol_short!("status"), course_id),
            is_active,
        );
    }

    /// Get total number of courses created
    pub fn get_course_count(env: Env) -> u64 {
        env.storage()
            .instance()
            .get(&symbol_short!("Count"))
            .unwrap_or(0)
    }

    /// Check if a course exists
    pub fn course_exists(env: Env, course_id: u64) -> bool {
        let course_key = (symbol_short!("Course"), course_id);
        env.storage().instance().has(&course_key)
    }
}

mod test;
