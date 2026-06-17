import sqlite3
import os
DB_PATH = os.path.join(os.path.dirname(__file__), "interview.db")
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Users Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        username TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    # 2. Questions Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        domain TEXT NOT NULL,
        difficulty TEXT NOT NULL, -- 'easy', 'medium', 'hard'
        question_text TEXT NOT NULL,
        ideal_answer TEXT NOT NULL,
        keywords TEXT NOT NULL -- Comma separated keywords
    )
    """)
    
    # 3. Sessions Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY,
        user_id INTEGER,
        domain TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        stress_mode INTEGER DEFAULT 0, -- 0 = Off, 1 = On
        coach_mode INTEGER DEFAULT 0, -- 0 = Off, 1 = On
        resume_text TEXT,
        overall_score REAL DEFAULT 0.0,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)
    
    # Check if user_id column exists (migration helper)
    cursor.execute("PRAGMA table_info(sessions)")
    columns = [col[1] for col in cursor.fetchall()]
    if "user_id" not in columns:
        cursor.execute("ALTER TABLE sessions ADD COLUMN user_id INTEGER REFERENCES users(id)")
    
    # 4. Responses Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS responses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        question_id INTEGER NOT NULL,
        candidate_answer TEXT,
        correctness_score REAL DEFAULT 0.0,
        relevance_score REAL DEFAULT 0.0,
        completeness_score REAL DEFAULT 0.0,
        feedback TEXT,
        eye_contact_score REAL DEFAULT 100.0,
        speaking_speed REAL DEFAULT 0.0,
        filler_words_count INTEGER DEFAULT 0,
        stress_score REAL DEFAULT 0.0,
        FOREIGN KEY(session_id) REFERENCES sessions(session_id),
        FOREIGN KEY(question_id) REFERENCES questions(id)
    )
    """)
    
    # Reset questions for rebuilding
    cursor.execute("DROP TABLE IF EXISTS questions")
    cursor.execute("""
    CREATE TABLE questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        domain TEXT NOT NULL,
        difficulty TEXT NOT NULL,
        question_text TEXT NOT NULL,
        ideal_answer TEXT NOT NULL,
        keywords TEXT NOT NULL
    )
    """)
    
    populate_default_questions(cursor)
        
    conn.commit()
    conn.close()
def populate_default_questions(cursor):
    questions_data = [
        # --- SOFTWARE DEVELOPMENT ---
        (
            "software_development", "easy",
            "Describe a scenario where you had to debug a production issue. How did you isolate the problem, what tools did you use, and what did you learn?",
            "To debug a production issue, first analyze logs and error messages using tools like ELK, Splunk, or APMs. Isolate the environment to reproduce the bug locally or in staging. Use debuggers, break points, network inspectors, or console tools to identify the root cause, apply a fix, verify it through testing, and deploy. Post-mortems or regression testing are added to prevent recurrence.",
            "logs,reproduce,isolate,debugger,root cause,post-mortem,regression testing"
        ),
        (
            "software_development", "medium",
            "In web applications, describe a situation where you had to choose between using a relational SQL database and a non-relational NoSQL database. What trade-offs did you consider?",
            "The choice depends on data structure, transaction reliability (ACID), and scalability. Relational databases like PostgreSQL are chosen for structured data requiring strong consistency and complex relationships. NoSQL databases like MongoDB or Cassandra are chosen for unstructured, flexible data schemas, rapid prototyping, horizontal scaling, or high-write volume where eventual consistency is acceptable.",
            "ACID,consistency,NoSQL,PostgreSQL,scalability,relationships,schema,eventual"
        ),
        (
            "software_development", "hard",
            "Explain the difference between process and thread concurrency models. If you were building a high-throughput chat server, how would you design it to avoid race conditions and deadlocks?",
            "Processes run in separate memory spaces, communicating via IPC, while threads share memory within the same process, requiring lower overhead but creating race risks. A high-throughput chat server can avoid race conditions and deadlocks using thread-safe data structures, synchronization locks (mutexes), lock-free queues, or asynchronous event-loop models like Node.js or Python's asyncio to process connections concurrently.",
            "processes,threads,shared memory,mutex,lock-free,event-loop,asyncio,deadlocks,race conditions"
        ),
        # --- DATA SCIENCE ---
        (
            "data_science", "easy",
            "Suppose your team trained a model with 98 percent accuracy on training data but it performs poorly on the production test set. How would you diagnose the issue and what techniques would you apply?",
            "This indicates overfitting, where the model fails to generalize. To diagnose, compare training curves with validation curves. Techniques to apply include cross-validation, regularization (L1/L2), pruning decision trees, simplifying the model architecture, feature selection to reduce noise, or gathering more diverse training data to improve generalization.",
            "overfitting,generalize,validation,regularization,cross-validation,pruning,complexity"
        ),
        (
            "data_science", "medium",
            "Explain the mathematical difference between L1 and L2 regularization. Under what data characteristics would you prefer one over the other?",
            "L1 regularization (Lasso) adds the absolute values of the coefficients as a penalty term to the loss function, which drives some weights to zero, acting as feature selection. L2 regularization (Ridge) adds the squared values of coefficients, shrinking weights close to zero but not exactly. Use L1 when you have high dimensionality and expect sparse features, and L2 when features are collinear and dense.",
            "L1,L2,absolute,squared,Lasso,Ridge,feature selection,coefficients,collinear"
        ),
        (
            "data_science", "hard",
            "Walk me through how you would handle severe class imbalance in a dataset for credit card fraud detection. What evaluation metrics would you focus on instead of standard accuracy?",
            "Severe class imbalance makes accuracy misleading. To address this, use resampling techniques like SMOTE (oversampling) or undersampling, or implement cost-sensitive learning. Focus on evaluation metrics like Precision, Recall, F1-Score, and Area Under the Precision-Recall Curve (PR-AUC) rather than ROC-AUC, ensuring low false negatives for fraud cases.",
            "imbalance,SMOTE,resampling,precision,recall,F1-Score,false negatives,PR-AUC"
        ),
        # --- AI / ML ---
        (
            "ai_ml", "easy",
            "Explain the vanishing gradient problem in deep neural networks. Which activation functions mitigate this issue, and how do they do so?",
            "The vanishing gradient occurs during backpropagation when gradients shrink exponentially as they propagate backward through layers, preventing weights from updating. It happens with sigmoid or tanh activations whose derivatives are less than one. We mitigate this by using ReLU (Rectified Linear Unit) or its variants (Leaky ReLU) because their derivative for positive inputs is constant at one, allowing gradients to flow unimpeded.",
            "vanishing gradient,backpropagation,activation,sigmoid,ReLU,derivative,constant"
        ),
        (
            "ai_ml", "medium",
            "Explain the core mechanics of the self-attention layer in the Transformer architecture. How does it handle sequence-to-sequence dependencies compared to older LSTM networks?",
            "Self-attention allows the model to process all tokens in a sequence simultaneously, calculating weights representing relationships between words regardless of distance. It computes Query, Key, and Value vectors, taking dot products to determine attention weights. LSTMs process text sequentially, causing information loss over long distances and preventing parallelization, which Transformers solve.",
            "Transformer,self-attention,Query Key Value,sequential,parallelization,LSTM,dependencies"
        ),
        (
            "ai_ml", "hard",
            "If you were designing a large language model fine-tuning pipeline on limited GPU resources, what optimization techniques (like LoRA or quantization) would you apply and how do they work?",
            "To fine-tune with limited GPUs, apply parameter-efficient fine-tuning (PEFT) like LoRA (Low-Rank Adaptation), which freezes base model weights and inserts small trainable rank decomposition matrices. Also use quantization (e.g. QLoRA) to compress 16-bit weights to 4-bit representation, reducing memory footprint. Other techniques include gradient accumulation and mixed-precision training.",
            "LoRA,quantization,QLoRA,parameter-efficient,memory footprint,decomposition,matrices,gradient accumulation"
        ),
        # --- HR ---
        (
            "hr", "easy",
            "Tell me about a time you had to work with a difficult stakeholder or team member. How did you manage the communication gap to ensure the project succeeded?",
            "To manage a difficult stakeholder, initiate active listening to understand their concerns, goals, and communication preferences. Frame discussions around objective project goals and metrics. Set clear expectations, establish regular status updates, separate personal friction from professional delivery, and seek win-win compromises to ensure project alignment.",
            "stakeholder,communication,active listening,expectations,compromise,collaboration,status updates"
        ),
        (
            "hr", "medium",
            "Walk me through a situation where you made a significant mistake on a project. How did you address the impact, and how did you prevent it from happening again?",
            "Explain the mistake objectively, take full accountability, and outline immediate mitigation actions. For prevention, establish code reviews, automated unit tests, validation checks, or updated documentation. This demonstrates accountability, problem-solving under stress, and learning from failure.",
            "mistake,accountability,mitigation,prevention,unit tests,code reviews,failure"
        ),
        (
            "hr", "hard",
            "If a project you are leading is falling behind schedule due to unexpected technical roadblocks, how do you handle negotiations with product management and the engineering team?",
            "Identify the roadblock and present transparent options: descoping non-essential features, extending the timeline, or staging releases. Align the engineering team on core tasks, communicate tradeoffs to product managers using data-backed velocity metrics, and negotiate a revised plan that maintains software quality without causing burnout.",
            "roadblocks,schedule,negotiation,descoping,tradeoffs,velocity,quality,burnout"
        ),
        # --- GENERAL (NEW) ---
        (
            "general", "easy",
            "Please introduce yourself, walk me through your academic or professional background, and tell me why you are interested in joining our company for this specific role.",
            "Introduce yourself clearly, highlighting relevant studies, key skills, and project experience. Express alignment with the company's culture, mission, and products, demonstrating that you have researched the role and company objectives.",
            "background,experience,skills,mission,culture,interested,goals"
        ),
        (
            "general", "medium",
            "What do you consider to be your greatest professional strength and your greatest weakness? How have you actively worked to improve on your weakness?",
            "Highlight a strength (e.g., technical problem solving, fast learning, collaboration) backed by an example. Share a real but manageable weakness (e.g., public speaking, perfectionism, over-committing) and describe the concrete steps you are taking to overcome it.",
            "strength,weakness,improvement,improve,examples,communication"
        ),
        (
            "general", "hard",
            "Where do you see yourself professionally in five years, and how do you envision this role acting as a catalyst for your long-term career goals?",
            "Express a desire to grow into senior technical roles, architecture design, or engineering leadership. Explain how the responsibilities, challenges, and learning opportunities in this target position directly build the expertise needed to achieve those goals.",
            "five years,career goals,growth,catalyst,leadership,senior,expertise"
        ),
        # --- SYSTEM DESIGN (NEW) ---
        (
            "system_design", "easy",
            "Explain the difference between vertical and horizontal scaling. When designing a system, at what point does vertical scaling become impractical?",
            "Vertical scaling involves adding more resources (CPU, RAM) to a single server, which is simple but has hardware limits and introduces a single point of failure. Horizontal scaling adds more servers to a pool, distributing load using load balancers. Vertical scaling becomes impractical when hardware costs escalate exponentially or physical limits of server boards are reached.",
            "vertical scaling,horizontal scaling,load balancer,hardware limits,single point of failure,servers"
        ),
        (
            "system_design", "medium",
            "How does a CDN (Content Delivery Network) improve application load times, and how do you handle cache invalidation when assets change frequently?",
            "A CDN caches static assets (images, CSS, JS) at edge servers closer to users, reducing network latency and server load. Cache invalidation can be managed using time-to-live (TTL) headers, purge requests, or versioned asset URLs (cache busting, e.g. script.v1.js or content hashing), which forces clients to fetch updated files immediately.",
            "CDN,cache,edge servers,latency,invalidation,TTL,cache busting,versioning"
        ),
        (
            "system_design", "hard",
            "Design a rate-limiting service for a high-traffic API gateway. What algorithm (e.g., Token Bucket, Sliding Window) would you use, and how would you store the rate-limit states across multiple server instances?",
            "To rate-limit a high-traffic API, use a Token Bucket or Sliding Window Log algorithm. To store client request counts across distributed instances, use a shared in-memory database like Redis for low-latency atomic operations (INCR, EXPIRE). Implement local in-memory backups or token buckets to handle Redis failover scenarios.",
            "rate-limiting,Token Bucket,Sliding Window,Redis,distributed,atomic,caching,API gateway"
        ),
        # --- DEVOPS & CLOUD (NEW) ---
        (
            "devops_cloud", "easy",
            "Explain the core principles of Infrastructure as Code (IaC). What are the benefits of using a tool like Terraform over manual cloud configuration?",
            "IaC manages and provisions infrastructure through machine-readable definition files instead of manual console work. Benefits include consistency (eliminating configuration drift), version control tracking, speed, scalability, documentation, and the ability to reproduce environments quickly using tools like Terraform.",
            "Infrastructure as Code,IaC,Terraform,configuration drift,version control,consistency,automation"
        ),
        (
            "devops_cloud", "medium",
            "Describe the architecture of a standard CI/CD pipeline. How do you implement blue-green deployments to ensure zero-downtime updates?",
            "A CI/CD pipeline automates code integration (build, test, lint) and delivery (deploy). Blue-green deployment runs two identical production environments: Blue (active) and Green (new release). Direct user traffic to Blue, deploy and test on Green, then switch the router/load balancer to point to Green, ensuring zero downtime and instant rollbacks.",
            "CI/CD,pipeline,blue-green,zero-downtime,load balancer,rollback,deployment"
        ),
        (
            "devops_cloud", "hard",
            "Suppose your Kubernetes cluster is experiencing crashloop backoffs on a stateful microservice. How would you troubleshoot this issue step-by-step from container to persistent volume layers?",
            "Troubleshoot by running 'kubectl describe pod' to check events, then check logs via 'kubectl logs'. If the container crashes due to database locking, inspect PersistentVolumeClaims (PVC) and PersistentVolumes (PV) to check binding states, check storage mounts, resource limits (OOM killed), read/write permissions on the mount, and network configurations.",
            "Kubernetes,crashloop backoff,kubectl,describe,logs,PersistentVolume,PVC,OOM,mount,permissions"
        )
    ]
    
    cursor.executemany("""
    INSERT INTO questions (domain, difficulty, question_text, ideal_answer, keywords)
    VALUES (?, ?, ?, ?, ?)
    """, questions_data)
if __name__ == "__main__":
    init_db()
    print("Database rebuilt and initialized with realistic questions successfully.")