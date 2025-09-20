import json

def aggregate_scores(
    hard_match_score: int,
    semantic_fit_score: int,
    llm_analysis_result: str, # Expecting the JSON string output from LLM
    hard_match_weight: float = 0.5,
    semantic_match_weight: float = 0.5
):
    # Validate weights
    if not (0 <= hard_match_weight <= 1 and 0 <= semantic_match_weight <= 1 and (hard_match_weight + semantic_match_weight) > 0):
        raise ValueError("Weights must be between 0 and 1 and their sum must be greater than 0.")

    # Normalize weights if their sum is not 1 (optional, but good for consistency)
    total_weight = hard_match_weight + semantic_match_weight
    normalized_hard_match_weight = hard_match_weight / total_weight
    normalized_semantic_match_weight = semantic_match_weight / total_weight

    # Calculate final relevance score
    final_relevance_score = int(
        (hard_match_score * normalized_hard_match_weight) +
        (semantic_fit_score * normalized_semantic_match_weight)
    )
    
    # Determine suitability verdict
    suitability_verdict = "Low"
    if final_relevance_score >= 80:
        suitability_verdict = "High"
    elif final_relevance_score >= 50:
        suitability_verdict = "Medium"

    # Parse LLM analysis result
    try:
        llm_data = json.loads(llm_analysis_result)
        missing_elements_from_llm = llm_data.get("missing_elements", [])
        
        # Extract missing elements and suggestions
        missing_skills_projects_certs = []
        improvement_suggestions = []
        for item in missing_elements_from_llm:
            element = item.get("element")
            suggestion = item.get("suggestion")
            if element:
                missing_skills_projects_certs.append(element)
            if suggestion:
                improvement_suggestions.append(suggestion)

    except json.JSONDecodeError:
        missing_skills_projects_certs = ["Could not parse LLM output for missing elements."]
        improvement_suggestions = ["Could not parse LLM output for suggestions."]
    except Exception as e:
        missing_skills_projects_certs = [f"Error processing LLM output: {str(e)}"]
        improvement_suggestions = [f"Error processing LLM output: {str(e)}]"]

    return {
        "final_relevance_score": final_relevance_score,
        "suitability_verdict": suitability_verdict,
        "missing_elements": missing_skills_projects_certs,
        "improvement_suggestions": improvement_suggestions
    }

if __name__ == "__main__":
    # Example usage
    sample_hard_match_score = 75
    sample_semantic_fit_score = 85
    sample_llm_output = '''{
        "match_score": 80,
        "missing_elements": [
            {"element": "Experience with FastAPI", "suggestion": "Highlight any experience with similar frameworks like Flask or Django and emphasize API development skills."},
            {"element": "Cloud Deployment (AWS/Azure)", "suggestion": "Gain certifications or complete projects involving cloud platforms like AWS or Azure."},
            {"element": "NoSQL Database experience", "suggestion": "Include projects or learning activities involving NoSQL databases like MongoDB or Cassandra."}
        ],
        "improvement_suggestions": [
            "Quantify achievements in your project descriptions (e.g., 'Increased performance by 15%').",
            "Add a 'Soft Skills' section, emphasizing communication, teamwork, and problem-solving.",
            "Include any certifications related to cloud platforms (AWS, Azure, GCP) or machine learning."
        ]
    }'''

    aggregated_result = aggregate_scores(
        hard_match_score=sample_hard_match_score,
        semantic_fit_score=sample_semantic_fit_score,
        llm_analysis_result=sample_llm_output,
        hard_match_weight=0.6,
        semantic_match_weight=0.4
    )
    print(json.dumps(aggregated_result, indent=4))

    # Example with different weights
    aggregated_result_2 = aggregate_scores(
        sample_hard_match_score,
        sample_semantic_fit_score,
        sample_llm_output,
        hard_match_weight=0.3,
        semantic_match_weight=0.7
    )
    print("\nWith different weights:")
    print(json.dumps(aggregated_result_2, indent=4))
