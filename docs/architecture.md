# Architecture Documentation

This document provides a detailed overview of the system design, database schema, and blockchain integration for LuminaLearn.

## System Design Overview

LuminaLearn is built using a layered architecture that separates concerns between the user interface, business logic, data persistence, and blockchain interaction.

```mermaid
graph TD
    subgraph Frontend["Frontend Layer"]
        UI[Web Interface] --> Templates[Django Templates]
        UI --> JS[JavaScript/Alpine.js]
        UI --> CSS[Tailwind CSS]
    end

    subgraph Application["Application Layer"]
        Django[Django Framework] --> Auth[Authentication System]
        Django --> BL[Business Logic]
        BL --> CourseM[Course Management]
        BL --> LectureM[Lecture Management]
        BL --> AttendanceM[Attendance Tracking]
        BL --> ReportM[Reporting & Analytics]
    end

    subgraph Data["Data Layer"]
        Models[Django Models] --> DB[(Database<br>SQLite/PostgreSQL)]
    end

    subgraph Blockchain["Blockchain Integration Layer"]
        Stellar[Stellar Blockchain] --> Contract[Smart Contract]
        Stellar --> Wallet[Wallet Management]
        Horizon[Horizon API] --- Stellar
        Soroban[Soroban RPC] --- Contract
    end

    %% Key Connections
    UI --> Django
    BL <--> Blockchain
    Models --- Django
```

## Database Schema

LuminaLearn uses a relational database to store application state. The following entity-relationship diagram illustrates the core models and their relationships.

```mermaid
erDiagram
    USER ||--o{ COURSE : "teaches"
    USER ||--o{ ENROLLMENT : "has"
    USER ||--o{ ATTENDANCE : "marks"
    COURSE ||--o{ ENROLLMENT : "contains"
    COURSE ||--o{ LECTURE : "has"
    LECTURE ||--o{ ATTENDANCE_SESSION : "has"
    LECTURE ||--o{ ATTENDANCE : "recorded_for"
    ATTENDANCE_SESSION ||--o{ ATTENDANCE : "validates"

    USER {
        string username
        string password
        boolean is_admin
        boolean is_teacher
        boolean is_student
        string stellar_public_key
        string stellar_seed
    }

    COURSE {
        string name
        string code
        datetime created_at
    }

    ENROLLMENT {
        string roll_number
        datetime enrollment_date
    }

    LECTURE {
        string title
        date date
        time start_time
        time end_time
        string blockchain_lecture_id
    }

    ATTENDANCE_SESSION {
        datetime start_time
        datetime end_time
        string nonce
        boolean is_active
        boolean blockchain_verified
    }

    ATTENDANCE {
        datetime timestamp
        boolean blockchain_verified
        string transaction_hash
    }
```

## API and Logic Flows

### User Registration and Blockchain Onboarding

When a user signs up, the system generates a Stellar account for them to enable blockchain-based verification.

```mermaid
sequenceDiagram
    participant User
    participant App
    participant Stellar
    
    User->>App: Register (Student/Teacher)
    App->>Stellar: Generate Keypair
    Stellar-->>App: Public Key & Secret
    App->>App: Save User with Keys
    App->>Stellar: Fund via Friendbot (Testnet)
    App->>Stellar: Register User on Smart Contract
    App-->>User: Welcome / Dashboard
```

### Attendance Marking Flow

Attendance is marked through a secure QR code system and verified on the Stellar blockchain.

```mermaid
sequenceDiagram
    participant Teacher
    participant Student
    participant App
    participant Stellar

    Teacher->>App: Start Attendance Session
    App->>App: Generate Nonce & QR Code
    App->>Stellar: Record Session (Optional)
    App-->>Teacher: Display QR Code
    
    Student->>App: Scan QR Code (Nonce)
    App->>App: Verify Nonce & Proximity
    App->>Stellar: Write Attendance Transaction
    Stellar-->>App: Tx Hash
    App->>App: Store Tx Hash & Verify
    App-->>Student: Success Message
```

## Blockchain Integration Details

### Stellar SDK and Soroban
LuminaLearn uses the [Stellar Python SDK](https://github.com/StellarCN/py-stellar-sdk) to interact with the Stellar network and Soroban smart contracts.

- **Account Management**: Keys are generated locally. In development, accounts are funded via Friendbot.
- **Smart Contracts**: Written in Rust for the Soroban platform. The contract handles the immutable storage of attendance mappings.
- **Verification**: Each attendance record in the database is linked to a `transaction_hash`, allowing for independent verification on any Stellar explorer.

### Security Note
In production, the `stellar_seed` must be encrypted at rest. Users should ideally manage their own keys via a wallet provider, but the current implementation manages keys on behalf of the user for ease of use in an educational environment.
