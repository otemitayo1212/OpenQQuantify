from flask import Flask, render_template, request, jsonify
import os
import sqlite3
import requests
import json
import logging
from dotenv import load_dotenv
from contextlib import contextmanager
from functools import wraps
import time
from generate_data import generate_quantum_data, save_to_database

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
DATABASE_PATH = os.getenv("DATABASE_PATH", "quantum_sims.db")
MAX_QUESTION_LENGTH = 1000
API_TIMEOUT = 30

# Validate required environment variables
if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY environment variable is required")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Rate limiting storage (in production, use Redis or similar)
request_timestamps = {}

def rate_limit(max_requests=10, window_seconds=60):
    """Simple rate limiting decorator"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            client_ip = request.remote_addr
            current_time = time.time()
            
            # Clean old timestamps
            if client_ip in request_timestamps:
                request_timestamps[client_ip] = [
                    ts for ts in request_timestamps[client_ip] 
                    if current_time - ts < window_seconds
                ]
            else:
                request_timestamps[client_ip] = []
            
            # Check rate limit
            if len(request_timestamps[client_ip]) >= max_requests:
                return jsonify({"error": "Rate limit exceeded. Try again later."}), 429
            
            # Add current request
            request_timestamps[client_ip].append(current_time)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@contextmanager
def get_db_connection():
    """Context manager for database connections"""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        yield conn
    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()

# Initialize database with fake quantum data
@app.cli.command("init-db")
def init_db():
    """Initialize database with quantum simulation data"""
    try:
        df = generate_quantum_data(100)
        save_to_database(df)
        logger.info("Database initialized with 100 fake quantum simulation records.")
        print("Database initialized with 100 fake quantum simulation records.")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        print(f"Error initializing database: {e}")

@app.route('/')
def quantum_simulator():
    """Main quantum simulator page"""
    return render_template('index.html')

def get_simulation_summary(limit=5):
    """Get a summary of recent quantum simulations"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT algorithm, 
                          AVG(accuracy) as avg_accuracy, 
                          AVG(runtime_ms) as avg_runtime,
                          COUNT(*) as simulation_count
                   FROM simulations 
                   GROUP BY algorithm 
                   ORDER BY avg_accuracy DESC 
                   LIMIT ?""", 
                (limit,)
            )
            rows = cursor.fetchall()
            
            if not rows:
                return "No quantum simulation data available yet."
            
            summary_lines = ["Recent quantum simulation performance:"]
            for row in rows:
                summary_lines.append(
                    f"- {row['algorithm']}: avg accuracy {row['avg_accuracy']:.2f}, "
                    f"avg runtime {row['avg_runtime']:.0f}ms ({row['simulation_count']} runs)"
                )
            return "\n".join(summary_lines)
            
    except sqlite3.Error as e:
        logger.error(f"Database error in get_simulation_summary: {e}")
        return "Unable to retrieve simulation data."

def validate_question(question):
    """Validate user input question"""
    if not question:
        return False, "No question provided"
    
    question = question.strip()
    if not question:
        return False, "Empty question"
    
    if len(question) > MAX_QUESTION_LENGTH:
        return False, f"Question too long (max {MAX_QUESTION_LENGTH} characters)"
    
    # Basic content filtering
    suspicious_keywords = ['<script', 'javascript:', 'data:', 'vbscript:']
    if any(keyword in question.lower() for keyword in suspicious_keywords):
        return False, "Invalid question content"
    
    return True, question

@app.route('/api/ask', methods=['POST'])
@rate_limit(max_requests=5, window_seconds=60)  # 5 requests per minute
def ask_quantum_ai():
    """Handle AI chat requests with improved error handling"""
    try:
        # Validate request data
        if not request.json:
            return jsonify({"error": "Invalid JSON data"}), 400
        
        user_question = request.json.get('question', '')
        is_valid, result = validate_question(user_question)
        
        if not is_valid:
            return jsonify({"error": result}), 400
        
        user_question = result  # Use cleaned question
        
        # Get simulation data summary
        data_summary = get_simulation_summary()
        
        # Prepare API request
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": request.host_url.rstrip('/'),
            "X-Title": "Quantum Simulator"
        }
        
        payload = {
            "model": "openai/gpt-4o",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a helpful quantum physics professor. Explain concepts clearly "
                        "with practical examples. Keep responses concise but informative.\n\n"
                        f"{data_summary}\n\n"
                        "Focus on practical applications and relate answers to simulation data when relevant. "
                        "If asked about topics outside quantum physics, politely redirect to quantum topics."
                    )
                },
                {"role": "user", "content": user_question}
            ],
            "max_tokens": 500,  # Limit response length
            "temperature": 0.7
        }
        
        # Make API request with timeout
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            data=json.dumps(payload),
            timeout=API_TIMEOUT
        )
        
        response.raise_for_status()
        data = response.json()
        
        # Validate response structure
        if 'choices' not in data or not data['choices']:
            logger.error(f"Invalid API response structure: {data}")
            return jsonify({"error": "Invalid response from AI service"}), 500
        
        ai_response = data["choices"][0]["message"]["content"]
        
        # Log successful interaction
        logger.info(f"AI question answered successfully for IP: {request.remote_addr}")
        
        return jsonify({"answer": ai_response})
        
    except requests.exceptions.Timeout:
        logger.error("OpenRouter API timeout")
        return jsonify({"error": "AI service is currently slow. Please try again."}), 504
    
    except requests.exceptions.RequestException as e:
        logger.error(f"OpenRouter API error: {e}")
        return jsonify({"error": "AI service temporarily unavailable"}), 503
    
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        return jsonify({"error": "Invalid response from AI service"}), 500
    
    except Exception as e:
        logger.error(f"Unexpected error in ask_quantum_ai: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

@app.route('/api/quantum-data')
def get_quantum_data():
    """Get quantum simulation data with pagination"""
    try:
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 50, type=int), 100)  # Max 100 per page
        offset = (page - 1) * per_page
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Get total count
            cursor.execute('SELECT COUNT(*) as total FROM simulations')
            total = cursor.fetchone()['total']
            
            # Get paginated data
            cursor.execute(
                'SELECT * FROM simulations ORDER BY simulation_id LIMIT ? OFFSET ?',
                (per_page, offset)
            )
            rows = cursor.fetchall()
            
            data = [dict(row) for row in rows]
            
            return jsonify({
                'data': data,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total,
                    'pages': (total + per_page - 1) // per_page
                }
            })
            
    except sqlite3.Error as e:
        logger.error(f"Database error in get_quantum_data: {e}")
        return jsonify({"error": "Database error occurred"}), 500
    
    except Exception as e:
        logger.error(f"Unexpected error in get_quantum_data: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT 1')
            cursor.fetchone()
        
        return jsonify({
            "status": "healthy",
            "database": "connected",
            "timestamp": time.time()
        })
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": time.time()
        }), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    # Only run in debug mode for development
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(debug=debug_mode, host='0.0.0.0', port=int(os.getenv('PORT', 5002)))