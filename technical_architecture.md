# LuminaLearn: Blockchain-Based Attendance System - Technical Architecture

## 1. System Overview

LuminaLearn is a web-based attendance management system that leverages the Stellar blockchain to provide secure, transparent, and tamper-proof attendance records. The system is designed for educational institutions to track student attendance in courses and lectures.

## 2. Architecture Components

### 2.1 Frontend Layer
- **Web Interface**: Django templates with Tailwind CSS for responsive UI
- **JavaScript**: Handles QR code scanning and dynamic content updates
- **Authentication UI**: Login, logout, and role-based signup flows

### 2.2 Application Layer
- **Django Framework**: Core web framework (MVC architecture)
- **Authentication System**: Custom user model with role-based permissions (Admin, Teacher, Student)
- **Business Logic**: 
  - Course management
  - Lecture scheduling
  - Attendance tracking
  - Reporting and analytics

### 2.3 Data Layer
- **Database**: SQLite (development), can be migrated to PostgreSQL for production
- **Models**:
  - User (extends Django's AbstractUser)
  - Course
  - Enrollment
  - Lecture
  - AttendanceSession
  - Attendance

### 2.4 Blockchain Integration Layer
- **Stellar Blockchain**: Public distributed ledger for attendance verification
- **Smart Contract**: Soroban-based contract for managing attendance records
- **Wallet Management**: Keypair generation and management for users

## 3. Data Flow

### 3.1 User Registration Flow
1. User signs up with credentials and is assigned a role (Admin/Teacher/Student)
2. System creates a Stellar keypair (public key + secret seed) for the user
3. Account is funded on Stellar testnet via Friendbot
4. User is registered on the blockchain smart contract
5. Credentials and blockchain details are stored in the database

### 3.2 Course Creation Flow
1. Teacher creates a new course with details
2. Course is stored in the database
3. Students can be enrolled in the course

### 3.3 Attendance Tracking Flow
1. Teacher initiates an attendance session for a lecture
2. System generates a secure nonce and creates QR code
3. Students scan QR code using their device
4. Attendance is verified and recorded on the blockchain
5. Transaction hash is stored as proof of attendance
6. Analytics are updated in real-time

## 4. Blockchain Implementation

### 4.1 Stellar Network Integration
- **Network**: Currently using Stellar Testnet
- **Horizon API**: Used for blockchain transactions and account management
- **Soroban RPC**: Used for smart contract interaction

### 4.2 Smart Contract Functionality
- Contract manages attendance records on-chain
- Attendance marking creates immutable records
- Verification can happen on or off-chain

### 4.3 Security Considerations
- Private keys are stored in the database (should be encrypted in production)
- QR codes with nonces prevent replay attacks
- Blockchain transactions provide audit trail and non-repudiation

## 5. Authentication & Authorization

### 5.1 User Roles
- **Admin**: System-wide access, can manage teachers and courses
- **Teacher**: Can create courses, manage lectures, and monitor attendance
- **Student**: Can view enrolled courses and mark their attendance

### 5.2 Permission Model
- Role-based access control
- View-level permissions enforced by decorators and mixins
- Template-level conditional rendering based on user role

## 6. API Endpoints

### 6.1 Authentication Endpoints
- `/login/` - User login
- `/logout/` - User logout
- `/admin/signup/` - Admin registration
- `/teacher/signup/` - Teacher registration
- `/student/signup/` - Student registration

### 6.2 Course Management Endpoints
- `/courses/` - List all accessible courses
- `/courses/create/` - Create a new course
- `/courses/<id>/` - Course details and management

### 6.3 Attendance Endpoints
- `/lectures/<id>/` - Lecture details and attendance management
- `/attendance/scan/` - QR code scanning interface
- `/attendance/process/` - Process scanned attendance data
- `/attendance/manual/<id>/` - Manual attendance marking
- `/attendance/sessions/<id>/close/` - Close an attendance session

### 6.4 Blockchain Endpoints
- `/blockchain/status/` - Check blockchain connection status
- `/blockchain/statistics/` - View blockchain statistics

## 7. Technical Stack

### 7.1 Frontend
- HTML5, CSS3 (Tailwind CSS)
- JavaScript (Alpine.js for interactivity)
- Responsive design with mobile support

### 7.2 Backend
- Python 3.x
- Django web framework
- Django ORM for database interaction

### 7.3 Blockchain
- Stellar SDK for Python
- Soroban smart contracts

### 7.4 Development & Deployment
- Development: Local environment with SQLite
- Production: To be deployed on cloud infrastructure with PostgreSQL
- Version control: Git

## 8. Future Enhancements

### 8.1 Technical Improvements
- Move to mainnet Stellar network
- Implement proper key encryption
- Add more sophisticated blockchain analytics
- Mobile app for easier QR scanning

### 8.2 Feature Roadmap
- Advanced reporting and analytics
- Integration with existing LMS systems
- Automated attendance reminders
- Biometric verification options

## 9. Project Structure

```
LuminaLearn/
│
├── attendance/                # Main application
│   ├── migrations/            # Database migrations
│   ├── templatetags/          # Custom template tags
│   ├── models.py              # Data models
│   ├── views.py               # View controllers
│   ├── forms.py               # Form definitions
│   ├── urls.py                # URL routing
│   ├── stellar_helper.py      # Blockchain integration
│   └── qr_utils.py            # QR code utilities
│
├── attendance_system/         # Project configuration
│   ├── settings.py            # Django settings
│   ├── urls.py                # Root URL routing
│   └── wsgi.py                # WSGI configuration
│
├── templates/                 # HTML templates
│   └── attendance/
│       ├── base.html          # Base template
│       ├── dashboard.html     # User dashboard
│       └── ...                # Other templates
│
├── static/                    # Static assets
│   ├── css/                   # CSS files
│   ├── js/                    # JavaScript files
│   └── img/                   # Images
│
└── manage.py                  # Django management script
``` 