from fasthtml.common import *
import json
import asyncio
from models.schema import questions, Question, responses, Response
from utils.session_manager import get_question_stats

def setup_websocket_routes(app):
    """
    Set up WebSocket routes for real-time updates
    """
    
    # Store active connections for each question
    question_connections = {}
    
    async def send_question_updates(question_id, send):
        """Send question statistics updates periodically"""
        try:
            while True:
                # Get the latest statistics
                stats = get_question_stats(question_id)
                
                # Format chart data based on question type
                question = questions[question_id]
                if not question:
                    break
                    
                if question.type == 'multiple_choice':
                    options = json.loads(question.options)
                    result_html = Div(
                        P(f"Total responses: {stats['response_count']}"),
                        Ul(*[Li(f"{option}: {stats['results'].get(option, 0)}") for option in options]),
                        cls="results-text"
                    )
                elif question.type == 'word_cloud':
                    word_list = [f"{word} ({count})" for word, count in stats['results'].items()]
                    result_html = Div(
                        P(f"Total responses: {stats['response_count']}"),
                        P(f"Unique words: {len(stats['results'])}"),
                        P(", ".join(word_list) if word_list else "No responses yet"),
                        cls="results-text"
                    )
                elif question.type == 'rating':
                    options = json.loads(question.options)
                    max_rating = options.get('max_rating', 5)
                    ratings = [str(i) for i in range(1, max_rating + 1)]
                    result_html = Div(
                        P(f"Total responses: {stats['response_count']}"),
                        Ul(*[Li(f"Rating {rating}: {stats['results'].get(rating, 0)}") for rating in ratings]),
                        cls="results-text"
                    )
                
                # Send update
                await send(result_html)
                
                # Wait before next update
                await asyncio.sleep(2)
        except Exception as e:
            print(f"Error in update loop: {e}")
        finally:
            # Remove from active connections when done
            if question_id in question_connections and send in question_connections[question_id]:
                question_connections[question_id].remove(send)
    
    @app.ws('/ws/results/{question_id}')
    async def results_ws(question_id: int, send):
        """WebSocket handler for real-time question results"""
        # Store connection
        if question_id not in question_connections:
            question_connections[question_id] = set()
        question_connections[question_id].add(send)
        
        # Start update task
        asyncio.create_task(send_question_updates(question_id, send))
        
        # Initial data
        stats = get_question_stats(question_id)
        return f"Connected. Monitoring results for question {question_id}. Total responses: {stats['response_count']}"

    return app
