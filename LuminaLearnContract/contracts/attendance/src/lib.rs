#![no_std]
use soroban_sdk::{
    contract, contracterror, contractimpl, log, symbol_short, Address, Env, Map,
    Symbol, BytesN, prng::Prng // Corrected Prng import, removed unused imports
};

// Define storage keys
const TEACHER: Symbol = symbol_short!("TEACHER");
const LECTURES: Symbol = symbol_short!("LECTURES"); // Map<u64, Address> lecture_id -> teacher_address
const SESSIONS: Symbol = symbol_short!("SESSIONS"); // Map<u64, (BytesN<32>, u64)> lecture_id -> (nonce, expiry_timestamp)
const RECORDS: Symbol = symbol_short!("RECORDS"); // Map<u64, Map<Address, bool>> lecture_id -> (student_address -> attended)

const STUDENTS: Symbol = symbol_short!("STUDENTS"); // Map<u64, Map<u64, StudentInfo>> lecture_id -> (roll_number -> StudentInfo)

#[derive(Clone, Debug, Eq, PartialEq)] // Added derive macros
#[soroban_sdk::contracttype] // Use contracttype macro
pub struct StudentInfo {
    name: soroban_sdk::String, // Use soroban_sdk::String
    // address: Option<Address>, // Optional: Store student address if needed later
}
// Define custom errors
#[contracterror]
#[derive(Copy, Clone, Debug, Eq, PartialEq, PartialOrd, Ord)]
#[repr(u32)]
pub enum Error {
    NotInitialized = 1,
    AlreadyInitialized = 2,
    Unauthorized = 3,
    LectureNotFound = 4,
    SessionNotActive = 5,
    SessionExpired = 6,
    InvalidNonce = 7,
    AlreadyMarked = 8,
    AttendancePeriodNotStarted = 9,
}

// Define data structures if needed (optional for this simple case)
// #[contracttype]
// pub struct Lecture {
//     id: u64,
//     teacher: Address,
// }

#[contract]
pub struct AttendanceContract;

#[contractimpl]
impl AttendanceContract {
    /// Initialize the contract, setting the teacher/admin.
    /// Can only be called once.
    pub fn initialize(env: Env, teacher: Address) -> Result<(), Error> {
        if env.storage().instance().has(&TEACHER) {
            return Err(Error::AlreadyInitialized);
        }
        env.storage().instance().set(&TEACHER, &teacher);
        // Initialize maps
        env.storage().persistent().set(&LECTURES, &Map::<u64, Address>::new(&env));
        env.storage().persistent().set(&SESSIONS, &Map::<u64, (BytesN<32>, u64)>::new(&env));
        env.storage().persistent().set(&RECORDS, &Map::<u64, Map<Address, bool>>::new(&env));
        env.storage().persistent().set(&STUDENTS, &Map::<u64, Map<u64, StudentInfo>>::new(&env)); // Initialize STUDENTS map
        Ok(())
    }

    /// Allows the teacher to create a new lecture entry.
    pub fn create_lecture(env: Env, teacher: Address, lecture_id: u64) -> Result<(), Error> {
        let stored_teacher = env.storage().instance().get(&TEACHER).ok_or(Error::NotInitialized)?;
        if teacher != stored_teacher {
            return Err(Error::Unauthorized);
        }
        teacher.require_auth(); // Ensure the caller is the teacher

        let mut lectures: Map<u64, Address> = env.storage().persistent().get(&LECTURES).unwrap(); // Should exist after init
        lectures.set(lecture_id, teacher.clone());
        env.storage().persistent().set(&LECTURES, &lectures);
        // Extend TTL for persistent storage
        // Assuming TTL values fit within u32
        env.storage().persistent().extend_ttl(&LECTURES, 100_000_u32, 500_000_u32); // Use u32 literals

        log!(&env, "Lecture created: {}", lecture_id);
        Ok(())
    }
/// Allows the teacher to add a student with roll number and name to a specific lecture.
    pub fn add_student(
        env: Env,
        teacher: Address,
        lecture_id: u64,
        roll_number: u64,
        name: soroban_sdk::String,
    ) -> Result<(), Error> {
        let stored_teacher = env.storage().instance().get(&TEACHER).ok_or(Error::NotInitialized)?;
        if teacher != stored_teacher {
            return Err(Error::Unauthorized);
        }
        teacher.require_auth(); // Ensure the caller is the teacher

        // Check if the lecture exists
        let lectures: Map<u64, Address> = env.storage().persistent().get(&LECTURES).ok_or(Error::LectureNotFound)?;
        if !lectures.contains_key(lecture_id) {
             return Err(Error::LectureNotFound);
        }

        // Get the main students map
        let mut all_students: Map<u64, Map<u64, StudentInfo>> = env.storage().persistent().get(&STUDENTS).unwrap(); // Should exist

        // Get or create the student map for this specific lecture
        let mut lecture_students: Map<u64, StudentInfo> = all_students
            .get(lecture_id)
            .unwrap_or_else(|| Map::new(&env));

        // Create student info
        let student_info = StudentInfo { name };

        // Add/update the student in the lecture's map
        lecture_students.set(roll_number, student_info);

        // Save the updated lecture's student map back to the main students map
        all_students.set(lecture_id, lecture_students);
        env.storage().persistent().set(&STUDENTS, &all_students);

        // Extend TTL for persistent storage
        env.storage().persistent().extend_ttl(&STUDENTS, 100_000_u32, 500_000_u32);

        log!(&env, "Student added/updated: Roll {}, Lecture {}", roll_number, lecture_id);
        Ok(())
    }

    /// Starts an attendance session for a given lecture.
    /// Generates a random nonce and sets an expiry time (e.g., 5 minutes).
    /// Returns the nonce to be used off-chain (e.g., in a QR code).
    pub fn start_attendance(env: Env, teacher: Address, lecture_id: u64, duration_seconds: u64) -> Result<BytesN<32>, Error> {
        let stored_teacher = env.storage().instance().get(&TEACHER).ok_or(Error::NotInitialized)?;
         if teacher != stored_teacher {
            return Err(Error::Unauthorized);
        }
        teacher.require_auth();

        let lectures: Map<u64, Address> = env.storage().persistent().get(&LECTURES).ok_or(Error::LectureNotFound)?;
        if !lectures.contains_key(lecture_id) {
             return Err(Error::LectureNotFound);
        }
        // Ensure the teacher calling is the one who created the lecture (or the main admin)
        // For simplicity now, only the main admin can start sessions
        // if lectures.get(lecture_id).unwrap() != teacher {
        //     return Err(Error::Unauthorized);
        // }


        // Generate a random nonce
        let mut prng = env.prng(); // Get Prng instance from Env
        let nonce: BytesN<32> = prng.gen();

        let current_timestamp = env.ledger().timestamp();
        let expiry_timestamp = current_timestamp + duration_seconds;

        let mut sessions: Map<u64, (BytesN<32>, u64)> = env.storage().persistent().get(&SESSIONS).unwrap();
        sessions.set(lecture_id, (nonce.clone(), expiry_timestamp));
        env.storage().persistent().set(&SESSIONS, &sessions);
        // Extend TTL for the session entry - should last slightly longer than the session itself
        // Cast duration to u32. Add checks if duration could exceed u32::MAX
        let extend_threshold: u32 = (duration_seconds + 60).try_into().unwrap_or(u32::MAX); // Handle potential overflow
        let extend_amount: u32 = (duration_seconds + 120).try_into().unwrap_or(u32::MAX); // Handle potential overflow
        env.storage().persistent().extend_ttl(&SESSIONS, extend_threshold, extend_amount);


        log!(&env, "Attendance started for lecture: {}, expires at: {}", lecture_id, expiry_timestamp);
        Ok(nonce)
    }

    /// Allows a student to mark their attendance using the nonce provided off-chain.
    pub fn mark_attendance(env: Env, student: Address, lecture_id: u64, nonce: BytesN<32>) -> Result<(), Error> {
        student.require_auth(); // Ensure the caller is the student

        let sessions: Map<u64, (BytesN<32>, u64)> = env.storage().persistent().get(&SESSIONS).ok_or(Error::AttendancePeriodNotStarted)?;
        let (stored_nonce, expiry_timestamp) = sessions.get(lecture_id).ok_or(Error::SessionNotActive)?;

        if env.ledger().timestamp() > expiry_timestamp {
            // Optional: Clean up expired session? Maybe not here to avoid extra cost.
            return Err(Error::SessionExpired);
        }

        if stored_nonce != nonce {
            return Err(Error::InvalidNonce);
        }

        // Get or create the attendance records map for this lecture
        let mut lecture_records: Map<Address, bool> = env
            .storage()
            .persistent()
            .get(&RECORDS)
            .and_then(|records_map: Map<u64, Map<Address, bool>>| { // Removed 'mut' here
                records_map.get(lecture_id)
            })
            .unwrap_or_else(|| Map::new(&env));


        if lecture_records.get(student.clone()).is_some() {
             return Err(Error::AlreadyMarked);
        }

        lecture_records.set(student.clone(), true);

        // Save the updated records for this lecture back into the main records map
        let mut all_records: Map<u64, Map<Address, bool>> = env.storage().persistent().get(&RECORDS).unwrap(); // Should exist
        all_records.set(lecture_id, lecture_records);
        env.storage().persistent().set(&RECORDS, &all_records);

        // Extend TTL for persistent storage
        // Assuming TTL values fit within u32
        env.storage().persistent().extend_ttl(&RECORDS, 100_000_u32, 500_000_u32); // Use u32 literals


        log!(&env, "Student {} marked attendance for lecture {}", student, lecture_id);
        Ok(())
    }

     /// Check if a student is marked present for a specific lecture.
    pub fn get_attendance(env: Env, lecture_id: u64, student: Address) -> bool {
        env.storage()
            .persistent()
            .get(&RECORDS)
            .and_then(|records_map: Map<u64, Map<Address, bool>>| {
                records_map.get(lecture_id)
            })
            .and_then(|lecture_records: Map<Address, bool>| {
                lecture_records.get(student)
            })
            .unwrap_or(false) // Default to false if lecture or student record doesn't exist
    }

    /// Get the teacher address.
    pub fn get_teacher(env: Env) -> Result<Address, Error> {
        env.storage().instance().get(&TEACHER).ok_or(Error::NotInitialized)
    }
}

mod test;