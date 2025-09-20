import os
import json
import logging
from datetime import datetime
from flask import Flask, jsonify, request
from backend.parser import parse_resume, parse_job_description # Import both functions
from backend.matcher import match_resume_to_jd # Import the matching function
from backend.semantic_matcher import calculate_semantic_fit_score # Import the semantic matching function
from backend.llm_analyzer import analyze_match, generate_feedback # Import both LLM functions
from backend.aggregator import aggregate_scores # Import the aggregation function
from backend.database.database import init_db, SessionLocal # Import database initialization and session
from backend.database.models import Resume, JobDescription, EvaluationResult, ImprovementSuggestion, AuditTrail # Import models

app = Flask(__name__)

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize database
@app.before_request
def initialize_database():
    # This ensures db initialization happens within app context
    # and only once per request, or when the first request comes in.
    # In a real app, you might want a more sophisticated init strategy.
    init_db()

# Helper function to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "ok", "time": datetime.now().isoformat()}), 200

@app.route('/')
def hello_world():
    return "Hello from Flask Backend!"

@app.route('/upload_resume', methods=['POST'])
def upload_resume():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        
        try:
            parsed_data = parse_resume(filepath)
            resume_text = parsed_data.get('raw_text', '') # Ensure raw_text is extracted
            
            db = SessionLocal()
            try:
                new_resume = Resume(filename=filename, raw_text=resume_text, parsed_data=json.dumps(parsed_data))
                db.add(new_resume)
                db.flush() # Flush to get the ID for audit trail
                
                audit_entry = AuditTrail(evaluation_id=None, action="Resume uploaded and parsed", details=f"Resume ID: {new_resume.id}, Filename: {filename}")
                db.add(audit_entry)
                db.commit()
                
                return jsonify({
                    'message': 'Resume uploaded and parsed successfully!', 
                    'resume_id': new_resume.id,
                    'parsed_data': parsed_data
                }), 200
            except Exception as e:
                db.rollback()
                return jsonify({'error': f'Database error: {str(e)}'}), 500
            finally:
                db.close()
        except Exception as e:
            return jsonify({'error': f'Error parsing resume: {str(e)}'}), 500
    return jsonify({'error': 'File type not allowed'}), 400

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in {'pdf', 'docx'}

from werkzeug.utils import secure_filename

@app.route('/upload_jd', methods=['POST'])
def upload_jd():
    jd_text = request.json.get('job_description', '')
    if not jd_text:
        return jsonify({'error': 'No job description provided'}), 400
    
    try:
        parsed_jd = parse_job_description(jd_text)
        
        db = SessionLocal()
        try:
            new_jd = JobDescription(role_title=parsed_jd.get('Role Title', 'N/A'), raw_text=jd_text, parsed_data=json.dumps(parsed_jd))
            db.add(new_jd)
            db.flush() # Flush to get the ID for audit trail
            
            audit_entry = AuditTrail(evaluation_id=None, action="Job Description uploaded and parsed", details=f"JD ID: {new_jd.id}, Role: {parsed_jd.get('Role Title', 'N/A')}")
            db.add(audit_entry)
            db.commit()
            
            return jsonify({
                'message': 'Job Description parsed successfully!', 
                'jd_id': new_jd.id,
                'parsed_data': parsed_jd
            }), 200
        except Exception as e:
            db.rollback()
            return jsonify({'error': f'Database error: {str(e)}'}), 500
        finally:
            db.close()
    except Exception as e:
        return jsonify({'error': f'Error parsing job description: {str(e)}'}), 500

@app.route('/match_resume_jd', methods=['POST'])
def match_resume_jd_endpoint():
    data = request.json
    parsed_resume = data.get('parsed_resume')
    parsed_jd = data.get('parsed_jd')

    if not parsed_resume or not parsed_jd:
        return jsonify({'error': 'Missing parsed resume or job description'}), 400

    hard_match_score = match_resume_to_jd(parsed_resume, parsed_jd)
    return jsonify({'match_percentage': hard_match_score}), 200

@app.route('/semantic_match', methods=['POST'])
def semantic_match_endpoint():
    data = request.json
    resume_text = data.get('resume_text')
    jd_text = data.get('jd_text')

    if not resume_text or not jd_text:
        return jsonify({'error': 'Missing resume_text or jd_text'}), 400

    semantic_fit_score = calculate_semantic_fit_score(resume_text, jd_text)
    return jsonify({'semantic_fit_score': semantic_fit_score}), 200

@app.route('/llm_analyze_match', methods=['POST'])
def llm_analyze_match_endpoint():
    data = request.json
    resume_text = data.get('resume_text')
    jd_text = data.get('jd_text')

    if not resume_text or not jd_text:
        return jsonify({'error': 'Missing resume_text or jd_text'}), 400

    llm_analysis = analyze_match(resume_text, jd_text)
    return jsonify(llm_analysis), 200

@app.route('/llm_feedback', methods=['POST'])
def llm_feedback_endpoint():
    data = request.json
    resume_text = data.get('resume_text')
    jd_text = data.get('jd_text')

    if not resume_text or not jd_text:
        return jsonify({'error': 'Missing resume_text or jd_text'}), 400

    llm_feedback = generate_feedback(resume_text, jd_text)
    return jsonify(llm_feedback), 200

@app.route('/aggregate_match_results', methods=['POST'])
def aggregate_match_results_endpoint():
    resume_filepath = None  # Initialize to None
    session = None
    try:
        # 1. Input Validation
        if "resume_file" not in request.files:
            logging.error("Validation Error: No resume file part in request.")
            return jsonify({"error": "No resume file part"}), 400

        resume_file = request.files["resume_file"]
        job_description_text = request.form.get("job_description_text", "")
        hard_match_weight_str = request.form.get("hard_match_weight")
        semantic_match_weight_str = request.form.get("semantic_match_weight")

        if resume_file.filename == "" or not job_description_text:
            logging.error("Validation Error: Missing resume file or job description text.")
            return jsonify({"error": "Missing resume file or job description text"}), 400

        try:
            hard_match_weight = float(hard_match_weight_str) if hard_match_weight_str else 0.5
            semantic_match_weight = float(semantic_match_weight_str) if semantic_match_weight_str else 0.5
            if not (0 <= hard_match_weight <= 1 and 0 <= semantic_match_weight <= 1):
                logging.error(f"Validation Error: Invalid weight values. Hard: {hard_match_weight}, Semantic: {semantic_match_weight}")
                return jsonify({"error": "Invalid hard_match_weight or semantic_match_weight. Must be between 0 and 1."}), 400
        except ValueError:
            logging.error(f"Validation Error: Could not convert weights to float. Hard: {hard_match_weight_str}, Semantic: {semantic_match_weight_str}", exc_info=True)
            return jsonify({"error": "Invalid format for hard_match_weight or semantic_match_weight"}), 400

        logging.debug(f"Received request for aggregation. Resume: {resume_file.filename}, JD length: {len(job_description_text)}, Weights: Hard={hard_match_weight}, Semantic={semantic_match_weight}")

        # Save resume file
        resume_filename = secure_filename(resume_file.filename)
        resume_filepath = os.path.join(UPLOAD_FOLDER, resume_filename)
        try:
            resume_file.save(resume_filepath)
            logging.debug(f"Resume file saved to {resume_filepath}")
        except Exception as e:
            logging.error(f"File Save Error: Could not save resume file {resume_filename}. Error: {e}", exc_info=True)
            return jsonify({"error": f"Could not save resume file: {str(e)}"}), 500

        parsed_resume_data = {}
        resume_raw_text = ""

        # 2. Parse Resume
        try:
            parsed_resume_data = parse_resume(resume_filepath)
            resume_raw_text = parsed_resume_data.get("raw_text", "")
            if not resume_raw_text:
                logging.warning(f"Resume Parsing Warning: No raw text extracted from {resume_filename}.")
            logging.debug(f"Resume parsed: {json.dumps(parsed_resume_data.get('Name', 'N/A'))}")
        except Exception as e:
            logging.error(f"Resume Parsing Error: Failed to parse resume file {resume_filename}. Error: {e}", exc_info=True)
            return jsonify({"error": f"Failed to parse resume: {str(e)}"}), 500

        # 3. Parse Job Description
        parsed_jd_data = {}
        try:
            parsed_jd_data = parse_job_description(job_description_text)
            if not parsed_jd_data.get('Role Title'):
                logging.warning("JD Parsing Warning: No role title extracted from JD.")
            logging.debug(f"JD parsed: {json.dumps(parsed_jd_data.get('Role Title', 'N/A'))}")
        except Exception as e:
            logging.error(f"JD Parsing Error: Failed to parse job description. Error: {e}", exc_info=True)
            return jsonify({"error": f"Failed to parse job description: {str(e)}"}), 500

        # 4. Hard Match
        hard_match_score = 0
        try:
            hard_match_score = match_resume_to_jd(parsed_resume_data, parsed_jd_data)
            logging.debug(f"Hard match score: {hard_match_score}")
        except Exception as e:
            logging.error(f"Hard Matching Error: Failed to compute hard match score. Error: {e}", exc_info=True)
            return jsonify({"error": f"Failed to compute hard match: {str(e)}"}), 500

        # 5. Semantic Match
        semantic_fit_score = 0
        try:
            semantic_fit_score = calculate_semantic_fit_score(resume_raw_text, job_description_text)
            logging.debug(f"Semantic fit score: {semantic_fit_score}")
        except Exception as e:
            logging.error(f"Semantic Matching Error: Failed to compute semantic fit score. Error: {e}", exc_info=True)
            return jsonify({"error": f"Failed to compute semantic match: {str(e)}"}), 500

        # 6. LLM Analysis
        llm_analysis = {}
        llm_feedback = {}
        try:
            llm_analysis = analyze_match(resume_raw_text, job_description_text)
            logging.debug(f"LLM analysis received: {llm_analysis}")
            llm_feedback = generate_feedback(resume_raw_text, job_description_text)
            logging.debug(f"LLM feedback received: {llm_feedback}")
        except Exception as e:
            logging.error(f"LLM Analysis Error: Failed to get LLM analysis or feedback. Error: {e}", exc_info=True)
            return jsonify({"error": f"Failed to get LLM analysis/feedback: {str(e)}"}), 500

        # 7. Aggregate Scores
        aggregated_results = {}
        try:
            aggregated_results = aggregate_scores(
                hard_match_score,
                semantic_fit_score,
                llm_analysis,
                hard_match_weight,
                semantic_match_weight
            )
            logging.debug(f"Aggregated results: {aggregated_results}")
        except Exception as e:
            logging.error(f"Aggregation Error: Failed to aggregate scores. Error: {e}", exc_info=True)
            return jsonify({"error": f"Failed to aggregate scores: {str(e)}"}), 500

        # 8. Database Operations
        session = SessionLocal()
        try:
            new_resume_db = Resume(filename=resume_filename, raw_text=resume_raw_text, parsed_data=json.dumps(parsed_resume_data))
            session.add(new_resume_db)
            session.flush()  # Get ID before commit

            new_jd_db = JobDescription(role_title=parsed_jd_data.get("Role Title", "N/A"), raw_text=job_description_text, parsed_data=json.dumps(parsed_jd_data))
            session.add(new_jd_db)
            session.flush()  # Get ID before commit
            
            evaluation_result = EvaluationResult(
                resume_id=new_resume_db.id,
                jd_id=new_jd_db.id,
                hard_match_score=hard_match_score,
                semantic_fit_score=semantic_fit_score,
                final_relevance_score=aggregated_results.get("final_relevance_score", 0),
                suitability_verdict=aggregated_results.get("suitability_verdict", "N/A"),
                llm_analysis_raw=json.dumps(llm_analysis)
            )
            session.add(evaluation_result)
            session.flush()  # Get ID before commit
            
            for suggestion_text in aggregated_results.get("improvement_suggestions", []):
                element_type = "general" 
                if "skills" in suggestion_text.lower():
                    element_type = "skills"
                elif "project" in suggestion_text.lower():
                    element_type = "projects"
                elif "certifications" in suggestion_text.lower():
                    element_type = "certifications"
                
                suggestion_entry = ImprovementSuggestion(
                    evaluation_id=evaluation_result.id,
                    element=element_type,
                    suggestion=suggestion_text
                )
                session.add(suggestion_entry)
            
            audit_entry = AuditTrail(
                evaluation_id=evaluation_result.id,
                action="Full pipeline executed",
                details=f"Resume ID: {new_resume_db.id}, JD ID: {new_jd_db.id}, Final Score: {aggregated_results.get('final_relevance_score', 0)}"
            )
            session.add(audit_entry)
            session.commit()
            logging.info(f"Aggregation results saved for Resume ID: {new_resume_db.id}, JD ID: {new_jd_db.id}")
            
            return jsonify({
                "message": "Aggregation complete and results saved!",
                "evaluation_id": evaluation_result.id,
                "results": aggregated_results
            }), 200
        except Exception as e:
            if session:
                session.rollback()
            logging.error(f"Database Error: Failed during database operations. Error: {e}", exc_info=True)
            return jsonify({"error": f"Database interaction error: {str(e)}"}), 500
        finally:
            if session:
                session.close()
            
    except Exception as e:
        logging.error(f"Unhandled Error in /aggregate_match_results: {e}", exc_info=True)
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500
    finally:
        if resume_filepath and os.path.exists(resume_filepath):
            os.remove(resume_filepath)
            logging.debug(f"Cleaned up uploaded resume file: {resume_filepath}")

@app.route('/evaluations', methods=['GET'])
def get_evaluations():
    db = SessionLocal()
    try:
        evaluations = db.query(EvaluationResult).all()
        results = []
        for eval_result in evaluations:
            resume = db.query(Resume).filter(Resume.id == eval_result.resume_id).first()
            jd = db.query(JobDescription).filter(JobDescription.id == eval_result.jd_id).first()
            suggestions = db.query(ImprovementSuggestion).filter(ImprovementSuggestion.evaluation_id == eval_result.id).all()
            audit_entries = db.query(AuditTrail).filter(AuditTrail.evaluation_id == eval_result.id).all()

            results.append({
                'evaluation_id': eval_result.id,
                'resume_filename': resume.filename if resume else 'N/A',
                'jd_role_title': jd.role_title if jd else 'N/A',
                'hard_match_score': eval_result.hard_match_score,
                'semantic_fit_score': eval_result.semantic_fit_score,
                'final_relevance_score': eval_result.final_relevance_score,
                'suitability_verdict': eval_result.suitability_verdict,
                'llm_analysis_raw': json.loads(eval_result.llm_analysis_raw) if eval_result.llm_analysis_raw else {},
                'evaluated_at': eval_result.evaluated_at.isoformat() if eval_result.evaluated_at else None,
                'improvement_suggestions': [{'element': s.element, 'suggestion': s.suggestion} for s in suggestions],
                'audit_trail': [{'action': a.action, 'timestamp': a.timestamp.isoformat(), 'details': a.details} for a in audit_entries]
            })
        return jsonify(results), 200
    except Exception as e:
        return jsonify({'error': f'Database fetch error: {str(e)}'}), 500
    finally:
        db.close()

if __name__ == '__main__':
    host = "127.0.0.1"
    port = 5000
    logging.info(f"Backend starting at http://{host}:{port}")
    app.run(host=host, port=port, debug=True)
