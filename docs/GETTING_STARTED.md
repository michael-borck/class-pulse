# Getting Started with ClassPulse

This guide will walk you through the setup, installation, and basic usage of ClassPulse, an interactive audience engagement tool.

## Prerequisites

- Python 3.8 or higher
- pip (Python package installer)
- Basic familiarity with terminal/command line

## Installation

1. **Clone the repository**

   ```bash
   git clone <repository-url>
   cd classpulse
   ```

2. **Create a virtual environment**

   ```bash
   python3 -m venv venv
   ```

3. **Activate the virtual environment**

   On macOS/Linux:
   ```bash
   source venv/bin/activate
   ```

   On Windows:
   ```cmd
   venv\Scripts\activate
   ```

4. **Install dependencies**

   ```bash
   pip install python-fasthtml
   ```

5. **Run the application**

   ```bash
   python app.py
   ```

6. **Access the application**

   Open your web browser and navigate to:
   ```
   http://localhost:5002
   ```

## Quick Start Guide

### For Presenters

1. **Login**
   - Use the default admin credentials:
     - Username: `admin`
     - Password: `admin123`

2. **Create a Session**
   - From the dashboard, click "Create New Session"
   - Enter a name for your session (e.g., "Python Workshop", "Marketing Presentation")
   - Click "Create Session"

3. **Add Questions**
   - On the session management page, you'll see options to add different types of questions
   - Click the appropriate button for the question type you want to create:
     - "New Multiple Choice" for multiple-choice questions
     - "New Word Cloud" for word cloud questions
     - "New Rating Scale" for rating questions

4. **Configure Your Questions**
   - **For Multiple Choice Questions**:
     - Enter the question title
     - Add options (one per line)
     - Click "Create Question"
   
   - **For Word Cloud Questions**:
     - Enter the question title
     - Click "Create Question"
   
   - **For Rating Scale Questions**:
     - Enter the question title
     - Specify maximum rating value (default is 5)
     - Click "Create Question"

5. **Activate Questions**
   - Questions are active by default
   - You can toggle questions on/off using the "Toggle Status" button

6. **Share Your Session**
   - Note the 6-digit session code displayed on the session management page
   - Share this code with your audience
   - Alternatively, share the QR code which will be displayed on the session page

7. **Present Mode**
   - Click "Present Mode" to enter the presentation view
   - This view shows real-time results as participants respond
   - The session code and QR code are prominently displayed for easy joining

8. **View Results**
   - Click "Results" next to any question to view detailed response data
   - Data is visualized according to the question type:
     - Bar charts for multiple choice
     - Word clouds for word cloud questions
     - Bar charts for rating scales

9. **Export Data**
   - From the question results page, click "Export Results" to download the data as CSV
   - From the session management page, click "Export" to download all session data

### For Audience Members

1. **Join a Session**
   - Navigate to the ClassPulse application (or dedicated join URL if provided)
   - Click "Join a session as audience" on the login page
   - Enter the 6-digit session code provided by the presenter
   - Click "Join"
   - Alternatively, scan the QR code if shown by the presenter

2. **Answer Questions**
   - You will see all active questions for the session
   - For each question type, the interface is slightly different:
   
   - **Multiple Choice Questions**:
     - Select your preferred option
     - Click "Submit Answer"
   
   - **Word Cloud Questions**:
     - Enter words or short phrases
     - Click "Submit Answer"
   
   - **Rating Scale Questions**:
     - Select a rating from the available options
     - Click "Submit Rating"

3. **Confirmation**
   - After submitting, you'll see a confirmation message
   - You can change your answers by submitting again if needed

## Using Question Types Effectively

### Multiple Choice Questions

**Best for:**
- Gauging opinion on specific options
- Testing knowledge with single correct answers
- Polls with distinct choices

**Tips:**
- Keep options clear and concise
- Avoid overlap between options
- Limit to 3-6 options for readability
- Consider including an "Other" option when appropriate

**Example:**
```
Which programming language are you most comfortable with?
- Python
- JavaScript
- Java
- C/C++
- Other
```

### Word Cloud Questions

**Best for:**
- Gathering diverse text responses
- Brainstorming sessions
- Collecting feedback in the participants' own words

**Tips:**
- Ask open-ended but focused questions
- Encourage participants to use single words or short phrases
- Let participants know multiple words create multiple entries
- Include clear context in the question

**Example:**
```
What words would you use to describe today's workshop?
```

### Rating Scale Questions

**Best for:**
- Satisfaction surveys
- Measuring agreement/disagreement
- Numerical feedback

**Tips:**
- Clearly define what the scale represents
- Consider using a 5-point scale for most purposes
- Adjust max rating to match your specific needs
- Include the scale context in the question

**Example:**
```
How useful did you find today's content? (1 = Not at all useful, 5 = Extremely useful)
```

## Best Practices for Effective Sessions

1. **Prepare Questions in Advance**
   - Create all your questions before the session starts
   - Test them to ensure they work as expected
   - Consider the flow of questions within your presentation

2. **Introduce the Tool**
   - Take a moment to explain how to join and participate
   - Demonstrate how to respond to each question type
   - Emphasize that responses are anonymous

3. **Balance Question Types**
   - Use multiple choice for specific, focused feedback
   - Use word clouds for creative, open-ended input
   - Use rating scales for quantifiable feedback

4. **Timing Matters**
   - Activate questions at appropriate moments during your presentation
   - Give sufficient time for responses (usually 30-60 seconds)
   - Deactivate questions when you're ready to move on

5. **Discuss Results**
   - Take time to acknowledge and discuss the results
   - Highlight interesting patterns or unexpected responses
   - Use the results to guide further discussion

6. **Follow Up**
   - Export session data for further analysis
   - Share results with participants if appropriate
   - Use insights to improve future sessions

## Customizing ClassPulse

ClassPulse is designed to be extensible. Some common customizations:

1. **Changing the Theme**
   - Edit `static/css/styles.css` to customize colors and styling

2. **Adding Question Types**
   - See the Developer Guide for instructions on adding new question types

3. **Custom Authentication**
   - Modify `utils/auth.py` to integrate with your authentication system

4. **Display Customizations**
   - Adjust chart appearance in `static/js/main.js`
   - Modify layout templates in `utils/components.py`

## Troubleshooting

### Common Issues

**Issue**: Application won't start
- Ensure Python 3.8+ is installed
- Verify the virtual environment is activated
- Check that you installed all dependencies
- Make sure no other application is using port 5002

**Issue**: Can't log in
- Default credentials are admin/admin123
- Check if the database file (classpulse.db) exists and isn't corrupted

**Issue**: Audience can't join session
- Verify the session is active (toggle if needed)
- Ensure the correct session code is being used
- Check that the audience is using the correct URL

**Issue**: Real-time updates not working
- Ensure WebSockets are supported in the browser
- Check network connectivity
- Verify that the presenter is in Present Mode

**Issue**: Charts not displaying
- Ensure JavaScript is enabled in the browser
- Check the browser console for errors
- Verify that responses have been submitted

## Next Steps

After getting familiar with the basic functionality, consider exploring:

1. **Advanced Features**
   - Explore the documentation on exporting and analyzing results
   - Try different question configurations for various scenarios

2. **Development**
   - Check the Developer Guide for information on extending the platform
   - Review the code structure to understand how components interact

3. **Feedback**
   - Use ClassPulse in real sessions and gather feedback
   - Contribute improvements to the project

For more detailed information, refer to other documentation:
- [API Reference](./API_REFERENCE.md)
- [Architecture](./ARCHITECTURE.md)
- [Developer Guide](./DEVELOPER_GUIDE.md)
- [Data Flow](./DATA_FLOW.md)
- [Technical Specification](./SPECIFICATION.md)
