from datetime import datetime
from models.schema import sessions, Session, questions, Question, responses, Response, generate_session_code
import json
from typing import List, Dict, Any

def create_session(user_id: int, name: str) -> Session:
    """
    Create a new presentation session
    """
    # Generate a unique code
    code = generate_session_code()
    while sessions(where="code = ?", where_args=[code]):
        code = generate_session_code()
    
    # Create the session
    session = Session(
        code=code,
        name=name,
        created_at=datetime.now().isoformat(),
        user_id=user_id,
        active=True
    )
    
    return sessions.insert(session)

def get_session_by_code(code: str) -> Session:
    """
    Get session by its code
    """
    session_list = sessions(where="code = ?", where_args=[code])
    return session_list[0] if session_list else None

def get_user_sessions(user_id: int) -> List[Session]:
    """
    Get all sessions for a user
    """
    return sessions(where="user_id = ?", where_args=[user_id], order_by="-created_at")

def toggle_session_status(session_id: int) -> bool:
    """
    Toggle a session between active and inactive
    """
    session = sessions[session_id]
    if not session:
        return False
    
    session.active = not session.active
    sessions.update(session)
    return session.active

def create_multiple_choice_question(session_id: int, title: str, options: List[str], order: int = 0) -> Question:
    """
    Create a multiple choice question
    """
    question = Question(
        session_id=session_id,
        type='multiple_choice',
        title=title,
        options=json.dumps(options),
        active=True,
        created_at=datetime.now().isoformat(),
        order=order
    )
    
    return questions.insert(question)

def create_word_cloud_question(session_id: int, title: str, order: int = 0) -> Question:
    """
    Create a word cloud question
    """
    question = Question(
        session_id=session_id,
        type='word_cloud',
        title=title,
        options='{}',  # No options for word cloud
        active=True,
        created_at=datetime.now().isoformat(),
        order=order
    )
    
    return questions.insert(question)

def create_rating_question(session_id: int, title: str, max_rating: int = 5, order: int = 0) -> Question:
    """
    Create a rating question
    """
    question = Question(
        session_id=session_id,
        type='rating',
        title=title,
        options=json.dumps({"max_rating": max_rating}),
        active=True,
        created_at=datetime.now().isoformat(),
        order=order
    )
    
    return questions.insert(question)

def get_session_questions(session_id: int) -> List[Question]:
    """
    Get all questions for a session
    """
    return questions(where="session_id = ?", where_args=[session_id], order_by="order")

def toggle_question_status(question_id: int) -> bool:
    """
    Toggle a question between active and inactive
    """
    question = questions[question_id]
    if not question:
        return False
    
    question.active = not question.active
    questions.update(question)
    return question.active

def record_response(question_id: int, session_id: int, value: str, respondent_id: str) -> Response:
    """
    Record a response to a question
    """
    # Check if this respondent has already answered this question
    existing = responses(where="question_id = ? AND respondent_id = ?", where_args=[question_id, respondent_id])
    
    # If they have, update their response
    if existing:
        existing_response = existing[0]
        existing_response.response_value = value
        existing_response.created_at = datetime.now().isoformat()
        return responses.update(existing_response)
    
    # Otherwise, create a new response
    response = Response(
        question_id=question_id,
        session_id=session_id,
        response_value=value,
        respondent_id=respondent_id,
        created_at=datetime.now().isoformat()
    )
    
    return responses.insert(response)

def get_question_responses(question_id: int) -> List[Response]:
    """
    Get all responses for a question
    """
    return responses(where="question_id = ?", where_args=[question_id])

def get_multiple_choice_results(question_id: int) -> Dict[str, int]:
    """
    Get results for a multiple choice question
    """
    question = questions[question_id]
    if not question or question.type != 'multiple_choice':
        return {}
    
    options = json.loads(question.options)
    responses_list = get_question_responses(question_id)
    
    # Initialize counts
    results = {option: 0 for option in options}
    
    # Count responses
    for response in responses_list:
        if response.response_value in results:
            results[response.response_value] += 1
    
    return results

def get_word_cloud_results(question_id: int) -> Dict[str, int]:
    """
    Get results for a word cloud question
    """
    question = questions[question_id]
    if not question or question.type != 'word_cloud':
        return {}
    
    responses_list = get_question_responses(question_id)
    
    # Count frequency of each word
    word_counts = {}
    for response in responses_list:
        words = response.response_value.lower().split()
        for word in words:
            # Remove any punctuation
            word = word.strip('.,;:!?()-\'"\\/[]{}')
            if word:
                word_counts[word] = word_counts.get(word, 0) + 1
    
    return word_counts

def get_rating_results(question_id: int) -> Dict[str, int]:
    """
    Get results for a rating question
    """
    question = questions[question_id]
    if not question or question.type != 'rating':
        return {}
    
    options = json.loads(question.options)
    max_rating = options.get('max_rating', 5)
    responses_list = get_question_responses(question_id)
    
    # Initialize counts
    results = {str(i): 0 for i in range(1, max_rating + 1)}
    
    # Count responses
    for response in responses_list:
        try:
            rating = response.response_value
            if rating in results:
                results[rating] += 1
        except (ValueError, KeyError):
            pass
    
    return results

def get_question_stats(question_id: int) -> Dict[str, Any]:
    """
    Get statistics for a question based on its type
    """
    question = questions[question_id]
    if not question:
        return {}
    
    responses_list = get_question_responses(question_id)
    response_count = len(responses_list)
    
    stats = {
        "question_id": question_id,
        "title": question.title,
        "type": question.type,
        "response_count": response_count,
    }
    
    if question.type == 'multiple_choice':
        stats["results"] = get_multiple_choice_results(question_id)
    elif question.type == 'word_cloud':
        stats["results"] = get_word_cloud_results(question_id)
    elif question.type == 'rating':
        stats["results"] = get_rating_results(question_id)
    
    return stats
