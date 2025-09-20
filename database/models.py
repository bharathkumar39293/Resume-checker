from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base # Import Base from your database.py

class Resume(Base):
    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    raw_text = Column(Text)
    parsed_data = Column(Text) # Store JSON string of parsed data
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())

    evaluations = relationship("EvaluationResult", back_populates="resume")

class JobDescription(Base):
    __tablename__ = "job_descriptions"

    id = Column(Integer, primary_key=True, index=True)
    role_title = Column(String, index=True)
    raw_text = Column(Text)
    parsed_data = Column(Text) # Store JSON string of parsed data
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    evaluations = relationship("EvaluationResult", back_populates="job_description")

class EvaluationResult(Base):
    __tablename__ = "evaluation_results"

    id = Column(Integer, primary_key=True, index=True)
    resume_id = Column(Integer, ForeignKey("resumes.id"))
    jd_id = Column(Integer, ForeignKey("job_descriptions.id"))
    hard_match_score = Column(Integer)
    semantic_fit_score = Column(Integer)
    final_relevance_score = Column(Integer)
    suitability_verdict = Column(String)
    llm_analysis_raw = Column(Text) # Store raw JSON output from LLM analysis
    evaluated_at = Column(DateTime(timezone=True), server_default=func.now())

    resume = relationship("Resume", back_populates="evaluations")
    job_description = relationship("JobDescription", back_populates="evaluations")
    suggestions = relationship("ImprovementSuggestion", back_populates="evaluation_result")
    audit_trail = relationship("AuditTrail", back_populates="evaluation_result")

class ImprovementSuggestion(Base):
    __tablename__ = "improvement_suggestions"

    id = Column(Integer, primary_key=True, index=True)
    evaluation_id = Column(Integer, ForeignKey("evaluation_results.id"))
    element = Column(String) # e.g., "Skills", "Certifications", "Projects"
    suggestion = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    evaluation_result = relationship("EvaluationResult", back_populates="suggestions")

class AuditTrail(Base):
    __tablename__ = "audit_trail"

    id = Column(Integer, primary_key=True, index=True)
    evaluation_id = Column(Integer, ForeignKey("evaluation_results.id"))
    action = Column(String) # e.g., "Resume uploaded", "JD parsed", "Evaluation completed"
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    details = Column(Text, nullable=True)

    evaluation_result = relationship("EvaluationResult", back_populates="audit_trail")
