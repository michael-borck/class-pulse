from fasthtml.common import *
import json
from datetime import datetime
from models.schema import sessions, Session, questions, Question, responses, Response
from utils.session_manager import (
    create_multiple_choice_question, create_word_cloud_question, create_rating_question,
    get_session_questions, toggle_question_status, get_question_stats
)
from utils.components import layout
import csv
import io

def setup_question_routes(rt):
    """
    Set up question-related routes
    """
    
    @rt("/sessions/{session_id}/questions/new/{type}")
    def get(session_id: int, type: str):
        """Create new question form"""
        # Validate question type
        if type not in ['multiple_choice', 'word_cloud', 'rating']:
            return RedirectResponse(f'/sessions/{session_id}', status_code=303)
        
        type_name = type.replace('_', ' ').title()
        
        form_content = [
            Div(
                Label("Question Title", For="title"),
                Input(id="title", name="title", required=True),
                cls="form-group"
            )
        ]
        
        if type == 'multiple_choice':
            form_content.extend([
                Div(
                    Label("Options (one per line)", For="options"),
                    Textarea(id="options", name="options", required=True),
                    cls="form-group"
                )
            ])
        elif type == 'rating':
            form_content.extend([
                Div(
                    Label("Maximum Rating", For="max_rating"),
                    Input(id="max_rating", name="max_rating", type="number", value="5", min="2", max="10", required=True),
                    cls="form-group"
                )
            ])
        
        return layout(
            H2(f"New {type_name} Question"),
            
            Form(
                *form_content,
                Button("Create Question", type="submit", cls="button primary"),
                method="post",
                action=f"/sessions/{session_id}/questions/new/{type}"
            ),
            
            title=f"New Question - ClassPulse"
        )

    @rt("/sessions/{session_id}/questions/new/multiple_choice")
    def post(session_id: int, title: str, options: str):
        """Create new multiple choice question"""
        # Split options by newline and filter out empty lines
        option_list = [opt.strip() for opt in options.split('\n') if opt.strip()]
        
        # Create the question
        create_multiple_choice_question(session_id, title, option_list)
        
        return RedirectResponse(f'/sessions/{session_id}', status_code=303)

    @rt("/sessions/{session_id}/questions/new/word_cloud")
    def post(session_id: int, title: str):
        """Create new word cloud question"""
        create_word_cloud_question(session_id, title)
        
        return RedirectResponse(f'/sessions/{session_id}', status_code=303)

    @rt("/sessions/{session_id}/questions/new/rating")
    def post(session_id: int, title: str, max_rating: int = 5):
        """Create new rating question"""
        # Ensure max_rating is within bounds
        max_rating = max(2, min(10, max_rating))
        
        create_rating_question(session_id, title, max_rating)
        
        return RedirectResponse(f'/sessions/{session_id}', status_code=303)

    @rt("/api/questions/{id}/toggle")
    def post(id: int):
        """Toggle question active status"""
        # Get question first to know which session it belongs to
        question = questions[id]
        if not question:
            return "Question not found"
        
        # Toggle status
        active = toggle_question_status(id)
        
        # Return updated button HTML
        return Div(
            Button(
                "Toggle Status",
                hx_post=f"/api/questions/{id}/toggle",
                hx_swap="outerHTML",
                hx_target=f"#question-{id}-actions"
            ),
            A("Edit", href=f"/questions/{id}/edit", cls="button"),
            A("Results", href=f"/questions/{id}/results", cls="button primary"),
            id=f"question-{id}-actions",
            cls="actions"
        )

    @rt("/questions/{id}/results")
    def get(id: int):
        """Question results page"""
        question = questions[id]
        if not question:
            return RedirectResponse('/sessions', status_code=303)
        
        # Get session info
        session_obj = sessions[question.session_id]
        
        # Get question statistics
        stats = get_question_stats(id)
        
        # Prepare chart data based on question type
        if question.type == 'multiple_choice':
            chart_type = 'bar'
            options = json.loads(question.options)
            data = {
                'labels': options,
                'datasets': [{
                    'label': 'Responses',
                    'data': [stats['results'].get(option, 0) for option in options],
                    'backgroundColor': ['#36a2eb', '#ff6384', '#4bc0c0', '#ffcd56', '#9966ff', '#ff9f40']
                }]
            }
        elif question.type == 'word_cloud':
            chart_type = 'wordCloud'
            # Format for jQCloud
            data = [{'text': word, 'weight': count} for word, count in stats['results'].items()]
        elif question.type == 'rating':
            chart_type = 'bar'
            options = json.loads(question.options)
            max_rating = options.get('max_rating', 5)
            ratings = [str(i) for i in range(1, max_rating + 1)]
            data = {
                'labels': ratings,
                'datasets': [{
                    'label': 'Responses',
                    'data': [stats['results'].get(rating, 0) for rating in ratings],
                    'backgroundColor': '#36a2eb'
                }]
            }
        
        return layout(
            H2(f"Results: {question.title}"),
            
            P(f"Session: {session_obj.name} (Code: {session_obj.code})"),
            P(f"Question type: {question.type.replace('_', ' ').title()}"),
            P(f"Total responses: {stats['response_count']}"),
            
            Div(
                # Container for chart
                Div(
                    id="chart-container",
                    data_chart_type=chart_type,
                    data_chart_data=json.dumps(data),
                    style="width: 100%; height: 400px;"
                ),
                cls="chart-wrapper"
            ),
            
            # Word cloud specific container
            Div(
                id="word-cloud-container",
                style="width: 100%; height: 400px; display: none;" if question.type != 'word_cloud' else "width: 100%; height: 400px;"
            ) if question.type == 'word_cloud' else None,
            
            Script(NotStr(f"""
                document.addEventListener('DOMContentLoaded', function() {{
                    const container = document.getElementById('chart-container');
                    const chartType = container.getAttribute('data-chart-type');
                    const chartData = JSON.parse(container.getAttribute('data-chart-data'));
                    
                    if (chartType === 'wordCloud') {{
                        // Handle word cloud visualization
                        $('#word-cloud-container').jQCloud(chartData, {{
                            width: 800,
                            height: 400,
                            colors: ['#36a2eb', '#ff6384', '#4bc0c0', '#ffcd56', '#9966ff']
                        }});
                    }} else {{
                        // Handle Chart.js visualizations
                        const ctx = document.createElement('canvas');
                        container.appendChild(ctx);
                        
                        new Chart(ctx, {{
                            type: chartType,
                            data: chartData,
                            options: {{
                                responsive: true,
                                scales: {{
                                    y: {{
                                        beginAtZero: true,
                                        ticks: {{
                                            precision: 0
                                        }}
                                    }}
                                }}
                            }}
                        }});
                    }}
                }});
            """)),
            
            Div(
                A("Back to Session", href=f"/sessions/{question.session_id}", cls="button"),
                A("Export Results", href=f"/questions/{id}/export", cls="button"),
                cls="actions-bar"
            ),
            
            title=f"Results: {question.title} - ClassPulse"
        )

    @rt("/questions/{id}/export")
    def get(id: int):
        """Export question results as CSV"""
        question = questions[id]
        if not question:
            return RedirectResponse('/sessions', status_code=303)
        
        # Get session info
        session_obj = sessions[question.session_id]
        
        # Get responses
        responses_list = responses(question_id=id)
        
        # Create CSV data
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write headers
        writer.writerow(['Question', 'Type', 'Response', 'Respondent ID', 'Timestamp'])
        
        # Write data
        for response in responses_list:
            writer.writerow([
                question.title,
                question.type,
                response.response_value,
                response.respondent_id,
                response.created_at
            ])
        
        # Create response with CSV content
        csv_content = output.getvalue()
        response = Response(
            content=csv_content,
            media_type="text/csv"
        )
        
        # Set filename in content-disposition header
        filename = f"question_{id}_{question.title.replace(' ', '_')}_results.csv"
        response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        
        return response

    @rt("/sessions/{id}/export")
    def get(id: int):
        """Export all session data as CSV"""
        session_obj = sessions[id]
        if not session_obj:
            return RedirectResponse('/sessions', status_code=303)
        
        # Get questions for this session
        session_questions = get_session_questions(id)
        
        # Create CSV data
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write headers
        writer.writerow(['Session', 'Question', 'Question Type', 'Response', 'Respondent ID', 'Timestamp'])
        
        # Write data for each question
        for question in session_questions:
            responses_list = responses(question_id=question.id)
            for response in responses_list:
                writer.writerow([
                    session_obj.name,
                    question.title,
                    question.type,
                    response.response_value,
                    response.respondent_id,
                    response.created_at
                ])
        
        # Create response with CSV content
        csv_content = output.getvalue()
        response = Response(
            content=csv_content,
            media_type="text/csv"
        )
        
        # Set filename in content-disposition header
        filename = f"session_{id}_{session_obj.name.replace(' ', '_')}_results.csv"
        response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        
        return response
        
    return rt
