# System Architecture Diagrams

These diagrams provide a comprehensive overview of the AI Attendance System, capturing the high-level flow, processing pipelines, database structure, and deployment architecture.

## 1. High-Level System Architecture Diagram

This diagram illustrates the core components of the system, separating the Frontend, Backend, and AI Modules, along with their primary connections.

```mermaid
flowchart TD
    subgraph Frontend [Frontend (React + Bootstrap)]
        SP[Student Portal]
        TP[Teacher/Admin Portal]
    end

    subgraph Backend [Backend (FastAPI/Node.js)]
        API[REST & WebSocket APIs]
        Auth[Authentication & RBAC]
        Core[Business Logic & Attendance Engine]
    end

    subgraph AI_Modules [AI & ML Processing]
        YOLO[YOLOv12 Face Detection]
        MediaPipe[MediaPipe Liveness]
        FaceNet[FaceNet Embeddings]
        FAISS[FAISS Similarity Search]
    end

    subgraph Database [Database (MongoDB/PostgreSQL)]
        Users[(Users/Roles)]
        Classes[(Classrooms)]
        Logs[(Attendance Logs)]
        Embeddings[(Vector Store)]
    end

    SP <-->|HTTP/WS| API
    TP <-->|HTTP/WS| API
    API --> Auth
    Auth --> Users
    API --> Core
    Core --> AI_Modules
    Core --> Classes
    Core --> Logs
    AI_Modules <--> Embeddings
```

## 2. Attendance Processing Pipeline

This diagram matches the "Live Attendance System" workflow you provided.

```mermaid
flowchart TD
    Start([Camera Input / Video Feed]) --> YOLO
    YOLO[YOLOv12 Face Detection]
    
    YOLO --> CheckFace{Face Detected?}
    CheckFace -- No --> Start
    CheckFace -- Yes --> MediaPipe[MediaPipe Liveness Check]
    
    MediaPipe --> CheckLiveness{Blink/Movement Verified?}
    CheckLiveness -- No --> Reject[Reject (Spoof)]
    CheckLiveness -- Yes --> FaceNet[FaceNet Extraction]
    
    FaceNet --> FAISS[FAISS Similarity Search]
    
    FAISS --> MatchCheck{Match > 70%?}
    MatchCheck -- Yes --> LogSuccess[Log Attendance]
    MatchCheck -- No --> LogUnknown[Unknown Person Alert]
    
    LogSuccess --> Start
    LogUnknown --> Start
    Reject --> Start
```

## 3. Authentication Flow Diagram

This diagram details the JWT and RBAC authentication process.

```mermaid
sequenceDiagram
    participant User as Client (Student/Admin)
    participant API as Auth API
    participant DB as Database
    
    User->>API: POST /login (Credentials)
    API->>DB: Query User & Verify Password
    DB-->>API: Return User Data & Role
    alt Invalid Credentials
        API-->>User: 401 Unauthorized
    else Valid Credentials
        API->>API: Generate JWT Token (Role Embedded)
        API-->>User: 200 OK + JWT Token
    end
    
    note over User,API: Subsequent Requests
    User->>API: Request Data + Auth Header (Bearer JWT)
    API->>API: Verify Token & Check RBAC
    alt Unauthorized Role
        API-->>User: 403 Forbidden
    else Authorized Role
        API->>DB: Fetch Data
        DB-->>API: Return Data
        API-->>User: 200 OK + JSON Response
    end
```

## 4. Database Schema

A conceptual Entity-Relationship representation of the core data models.

```mermaid
erDiagram
    USER ||--o{ ATTENDANCE : "marks"
    USER {
        string _id PK
        string role "student, teacher, admin"
        string email
        string password_hash
        string full_name
        string face_embedding_id FK
    }
    CLASSROOM ||--o{ ATTENDANCE : "has"
    CLASSROOM ||--o{ USER : "enrolled"
    CLASSROOM {
        string _id PK
        string name
        string teacher_id FK
        string schedule
    }
    ATTENDANCE {
        string _id PK
        string user_id FK
        string classroom_id FK
        timestamp timestamp
        float confidence_score
        string camera_id
    }
    VECTOR_STORE ||--o| USER : "belongs to"
    VECTOR_STORE {
        string embedding_id PK
        floatArray vector_data
    }
```

## 5. API Workflow Diagram

Illustrates the flow for a specific dashboard request, such as fetching student analytics.

```mermaid
flowchart LR
    Client(Browser/Client) -->|GET /api/analytics/student/123| Router[API Router]
    Router --> Middleware[JWT/RBAC Middleware]
    
    Middleware -- Valid --> Controller[Analytics Controller]
    Middleware -- Invalid --> ErrorResp[401/403 Response]
    
    Controller --> DBQuery[(Database Query)]
    DBQuery --> Controller
    Controller --> DataFormatter[Format Chart Data]
    DataFormatter --> Response[200 OK Response]
    Response --> Client
```

## 6. Real-Time Attendance Workflow Visualization

Details how the WebSocket pushes live updates to the teacher's dashboard.

```mermaid
sequenceDiagram
    participant Camera
    participant Server as AI Server
    participant DB as Database
    participant WS as WebSocket Server
    participant Client as Teacher Dashboard

    Client->>WS: Connect to Live Class Room ID
    WS-->>Client: Connection Established
    
    loop Every Frame
        Camera->>Server: Send Frame
        Server->>Server: Process (YOLO -> Liveness -> FAISS)
        alt Attendance Logged
            Server->>DB: Insert Attendance Record
            Server->>WS: Broadcast {user_id, status: "Present"}
            WS->>Client: Update Live Roster UI
        end
    end
```

## 7. Deployment Architecture

Shows the infrastructure layout for a production environment.

```mermaid
flowchart TD
    subgraph Cloud [Cloud Infrastructure]
        subgraph Vercel [Frontend Hosting]
            UI[React/Vite App]
        end
        
        subgraph Server [Backend / AI Processing Server]
            API_Gateway[Nginx / API Gateway]
            FastAPI[FastAPI Application]
            AI_Workers[AI Background Workers]
        end
        
        subgraph Data [Data Layer]
            DB[(Primary Database)]
            VectorDB[(FAISS Vector Store)]
            Storage[(Cloud Storage - S3)]
        end
    end
    
    Internet((Internet)) --> UI
    Internet --> API_Gateway
    UI -->|API Requests| API_Gateway
    
    API_Gateway --> FastAPI
    FastAPI --> AI_Workers
    
    FastAPI --> DB
    AI_Workers --> VectorDB
    AI_Workers --> Storage
```
