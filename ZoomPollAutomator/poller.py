# poller.py
import json
import requests
import re
# Using openai library which can interface with Ollama's API
from openai import OpenAI
import logging
import config # Import config to get Ollama host and Zoom token

logger = logging.getLogger(__name__)

# Using the OpenAI client for compatibility with Ollama's API
# The base_url is set to the Ollama host from config
ollama_client = None # Initialize later to use config


def get_ollama_client():
    """Initializes and returns the Ollama client."""
    global ollama_client
    if ollama_client is None:
        ollama_host_v1 = config.get_config("OLLAMA_HOST") # Get the V1 API endpoint from config
        if not ollama_host_v1:
             logger.error("Ollama host is not configured. Cannot create Ollama client.")
             return None
        try:
            ollama_client = OpenAI(base_url=ollama_host_v1, api_key="ollama") # api_key can be anything for Ollama
            logger.info(f"Ollama client initialized with base_url: {ollama_host_v1}")
        except Exception as e:
            logger.error(f"Error initializing Ollama client with base_url {ollama_host_v1}: {e}", exc_info=True)
            return None
    return ollama_client


# Poll prompt - Keep the same effective prompt
POLL_PROMPT = """
You are an expert meeting assistant tasked with creating a highly accurate and relevant poll based solely on the provided meeting transcript. Your objective is to generate a poll consisting of an eye-catching title, a specific question tied to the discussion, and exactly four distinct options, all derived directly from the transcript's content. The poll must reflect the key points, opinions, or decisions discussed, ensuring 100% relevance to the transcript without introducing external information or assumptions. Follow these steps to generate the poll:

1. **Transcript Analysis**:
   - Carefully read and analyze the entire transcript to understand its context, main topic, and key points.
   - Identify the central theme or focus of the discussion (e.g., a decision to be made, a topic debated, or a key insight).
   - Note any explicit statements, opinions, suggestions, or perspectives expressed by participants.
2. **Title Generation**:
   - Create a concise, engaging, and professional title that captures the essence of the discussion.
   - Make the title eye-catching by highlighting the most interesting or significant aspect of the transcript (e.g., a point of contention, a critical decision, or a standout theme).
   - Ensure the title is directly inspired by the transcript's content.
3. **Question Formulation**:
   - Formulate a clear and specific question that prompts participants to reflect on a significant aspect of the meeting.
   - Tailor the question to the transcript's key focus, such as a decision needing input, a debated topic, or a critical takeaway.
   - Avoid generic or pre-made questions; the question must be uniquely tied to the discussion.
4. **Options Creation**:
   - Select or summarize exactly four distinct statements, opinions, or perspectives from the transcript to serve as the poll options.
   - Use direct quotes where possible, or create close paraphrases that preserve the original meaning when quotes are lengthy or need slight rephrasing for clarity.
   - Ensure the options represent the range of views or points raised in the discussion and are mutually exclusive where applicable.
   - If the transcript contains fewer than four distinct points, creatively adapt the available content (e.g., by splitting a complex statement into two options or emphasizing different aspects of a single point), but remain strictly within the transcript's boundaries.
5. **Handling Edge Cases**:
   - **Short Transcripts**: If the transcript is very short (e.g., fewer than 50 words), focus on the available content to generate a meaningful poll. Use the limited text to craft a title, question, and options that reflect what is present, avoiding filler or generic content.
   - **Long Transcripts**: If the transcript is lengthy, prioritize the most salient points or the most recent/impactful discussion to ensure the poll remains focused and relevant.
6. **Strict Adherence to Transcript Content**:
   - Never invent content or add information not found in the transcript.
   - Use exact phrasing from the transcript whenever possible.
   - Your options MUST be derived directly from what was said in the transcript.
   - If the transcript discusses multiple topics, choose the most prominent or recent one.
7. **Output Format**:
   - Provide the poll in the following JSON format ONLY:
     ```json
     {
       "title": "Engaging Title",
       "question": "Specific Question?",
       "options": ["Statement 1", "Statement 2", "Statement 3", "Statement 4"]
     }
     ```
   - Do not include any additional explanation or text outside of this JSON structure.
Additional Guidelines:
- Maintain a professional yet engaging tone suitable for a meeting context.
- Do not invent content or assume details not present in the transcript.
- If the transcript lacks explicit options, distill the discussion into four representative choices based on implied perspectives or key statements.
Transcript:
[Insert transcript here]
"""

def extract_json_from_text(text):
    """
    Extracts JSON from text that might contain markdown or other text.
    Args:
        text (str): Text containing JSON (possibly with other content)

    Returns:
        dict: Parsed JSON object or None if not found or invalid format.
    """
    # Look for a JSON object structure in the text
    json_pattern = r'\{(?:[^{}]|(?:\{(?:[^{}]|(?:\{[^{}]*\}))*\}))*\}'
    match = re.search(json_pattern, text, re.DOTALL) # Use re.DOTALL to match across newlines

    if match:
        json_str = match.group(0)
        try:
            # Attempt to parse the extracted string as JSON
            poll_data = json.loads(json_str)
            # Basic validation for expected keys and structure
            if isinstance(poll_data, dict) and \
               "title" in poll_data and isinstance(poll_data["title"], str) and \
               "question" in poll_data and isinstance(poll_data["question"], str) and \
               "options" in poll_data and isinstance(poll_data["options"], list) and \
               len(poll_data["options"]) >= 1 and all(isinstance(opt, str) for opt in poll_data["options"]):
                return poll_data
            else:
                logger.warning("Extracted JSON does not match expected poll structure.")
                return None # Return None if structure is unexpected
        except json.JSONDecodeError as e:
            logger.warning(f"JSON decode error on extracted string: {e}")
            return None # Return None if extracted string is not valid JSON
    else:
        logger.warning("No JSON object found in the text using regex.")
        return None


def generate_poll_from_transcript(transcript: str) -> tuple[str, str, list[str]]:
    """
    Generate a poll (title, question, options) from a transcript using the local Ollama model.

    Args:
        transcript (str): The meeting transcript to analyze.
        model_name (str): The Ollama model name to use for generation.

    Returns:
        tuple: (title, question, options) of the generated poll. Returns default/fallback values on error or invalid output.
    """
    client = get_ollama_client()
    if client is None:
        logger.error("Ollama client is not available. Cannot generate poll.")
        # Return a fallback poll indicating an issue
        return ("Poll Generation Error", "Could not connect to Ollama.", ["Check Ollama server", "See logs for details", "Option 3", "Option 4"])

    clean_transcript = transcript.strip()
    if not clean_transcript:
        logger.warning("⚠️ Empty transcript provided for poll generation.")
        # Return a generic fallback poll for empty input
        return ("Meeting Poll", "What was discussed?",
                ["(No transcript audio)", "Option 2", "Option 3", "Option 4"])

    full_prompt = POLL_PROMPT.replace("[Insert transcript here]", clean_transcript)
    logger.info("🤖 Generating poll from transcript…")
    logger.debug(f"Prompting LLM with transcript length: {len(clean_transcript)} characters")

    # Get the model name from config or a default if not set/found
    ollama_model_name = config.get_config("OLLAMA_MODEL_NAME") or "deepseek-r1:1.5b"
    logger.debug(f"Using Ollama model: {ollama_model_name}")

    try:
        # Request poll from Ollama
        resp = client.chat.completions.create(
            model=ollama_model_name, # Use the configured model name
            messages=[{"role": "user", "content": full_prompt}],
            temperature=0.7, # Adjust for desired creativity
            max_tokens=800,  # Increased to allow for complete responses
            response_format={"type": "json_object"} # Request JSON response
        )
        raw_response = resp.choices[0].message.content.strip()
        logger.info(f"📥 Ollama raw response received ({len(raw_response)} chars). Attempting to parse JSON.")
        logger.debug(f"Raw LLM response: {raw_response}")

        # Try to extract and parse JSON from the response
        poll_data = extract_json_from_text(raw_response)

        # If we couldn't extract or parse JSON successfully
        if poll_data is None:
            logger.warning("⚠️ Failed to extract or parse JSON from LLM response.")
            # Try a basic parse as a fallback, in case extract_json_from_text was too strict
            try:
                 poll_data = json.loads(raw_response)
                 logger.info("Successfully parsed raw response directly as JSON.")
                 # Basic validation for expected keys and structure
                 if not (isinstance(poll_data, dict) and
                         "title" in poll_data and isinstance(poll_data["title"], str) and
                         "question" in poll_data and isinstance(poll_data["question"], str) and
                         "options" in poll_data and isinstance(poll_data["options"], list) and
                         len(poll_data["options"]) >= 1 and all(isinstance(opt, str) for opt in poll_data["options"])):
                      logger.warning("Directly parsed JSON does not match expected poll structure.")
                      poll_data = None # Treat as invalid if structure is wrong

            except json.JSONDecodeError as e:
                logger.error(f"❌ JSON parsing error on raw response:[/] {e}")
                logger.debug(f"Raw response that failed JSON parse: {raw_response[:200]}...")
                poll_data = None # Ensure poll_data is None on error

        # If after all attempts, poll_data is still None, use fallback
        if poll_data is None:
            logger.error("❌ Poll generation failed: Invalid or unparsable response from LLM.")
            # Create a fallback poll that indicates there was an error
            fallback_title = "Poll Generation Failed"
            fallback_question = "Could not generate poll from transcript."
            fallback_options = [
                "Check Ollama server status",
                "Review application logs",
                "Try transcribing again",
                "Use manual poll"
            ]
            return fallback_title, fallback_question, fallback_options


        # Extract and validate components from successfully parsed JSON
        title = poll_data.get("title", "Meeting Poll")
        question = poll_data.get("question", "What was the main topic discussed?")
        options = poll_data.get("options", [])

        # Validate and adjust options to ensure exactly 4 string options
        if not isinstance(options, list) or not all(isinstance(opt, str) for opt in options):
            logger.warning("⚠️ Options in LLM response are not a list of strings. Creating defaults.")
            options = [] # Reset options if invalid format

        # Make sure we have exactly 4 options
        while len(options) < 4:
            options.append(f"Additional Point {len(options) + 1}") # Add placeholder options

        if len(options) > 4:
            logger.warning(f"⚠️ Too many options ({len(options)}). Truncating to 4.")
            options = options[:4]

        # Log success
        logger.info("✅ Successfully generated poll data.")
        logger.debug(f"Generated Poll: Title='{title}', Question='{question}', Options={options}")

        return title, question, options

    except Exception as e:
       logger.error(f"❌ Unexpected error during poll generation: {e}", exc_info=True)

       # Create a fallback poll for any unexpected errors
       fallback_title = "Poll Generation Error"
       fallback_question = "An error occurred during poll generation."
       fallback_options = [
           "Check Ollama server connection",
           "Review application logs",
           "Try transcribing again",
           "Contact support"
       ]

       return fallback_title, fallback_question, fallback_options


def post_poll_to_zoom(title: str, question: str, options: list[str], meeting_id: str, token: str) -> bool:
    """
    Post a poll to a Zoom meeting using the Zoom API.

    Args:
        title (str): Poll title.
        question (str): Poll question.
        options (list[str]): List of poll options (will be truncated/padded to 4).
        meeting_id (str): Zoom meeting ID.
        token (str): Zoom API access token.

    Returns:
        bool: True if successful (status code 201), False otherwise.
    """
    url = f"https://api.zoom.us/v2/meetings/{meeting_id}/polls"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Ensure we have exactly 4 options for the Zoom API
    poll_options = options[:] # Create a copy
    while len(poll_options) < 4:
        poll_options.append(f"Option {len(poll_options) + 1}")
    if len(poll_options) > 4:
        poll_options = poll_options[:4]


    payload = {
        "title": title,
        "questions": [{
            "name": question,
            "type": "single", # Zoom Poll API type: single or multiple
            "answer_required": True,
            "answers": poll_options
        }]
    }

    logger.info(f"📤 Attempting to post poll to Zoom Meeting ID {meeting_id}:")
    logger.debug(f"Payload: {json.dumps(payload)}")

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10) # Added timeout
        if response.status_code == 201:
            logger.info(f"[green]✅ Poll posted successfully.[/] Response: {response.json()}")
            return True
        elif response.status_code == 401:
             logger.error(f"❌ Zoom API error {response.status_code}: Unauthorized. Token may be invalid or expired.")
             logger.error(f"Response body: {response.text}")
             # Signal to the GUI that the token might be expired and needs re-authorization
             try:
                 from main_gui import gui_queue
                 if gui_queue:
                      gui_queue.put(('STATUS', "[red]❌ Zoom token expired or invalid. Please re-authenticate with Zoom.[/]"))
             except ImportError:
                  pass # Ignore if gui_queue is not available
             return False
        else:
            logger.error(f"❌ Zoom API error posting poll: {response.status_code} - {response.text}")
            return False
    except requests.exceptions.RequestException as e:
       logger.error(f"❌ Network or request error posting poll to Zoom: {e}", exc_info=True)
       return False
    except Exception as e:
       logger.error(f"❌ Unexpected error posting poll to Zoom: {e}", exc_info=True)
       return False

if __name__ == "__main__":
    # Example usage for testing poller.py directly
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.info("Testing poller.py - Simulating poll generation and post.")

    # --- Simulate Config ---
    class MockConfig:
        _settings = {}
        def get_config(self, key):
            return self._settings.get(key)
        def set_config(self, key, value):
            self._settings[key] = value

    mock_config = MockConfig()
    mock_config.set_config("OLLAMA_HOST_BASE", "http://localhost:11434")
    mock_config.set_config("OLLAMA_HOST", "http://localhost:11434/v1") # Set derived URL
    mock_config.set_config("OLLAMA_API", "http://localhost:11434") # Set derived URL
    mock_config.set_config("OLLAMA_MODEL_NAME", "deepseek-r1:1.5b") # Configure a model name
    mock_config.set_config("ZOOM_TOKEN", "YOUR_FAKE_ZOOM_TOKEN") # Replace with a real token for post test
    mock_config.set_config("MEETING_ID", "YOUR_FAKE_MEETING_ID") # Replace with a real ID for post test

    # Replace the actual config module with the mock for testing
    config = mock_config

    # --- Test Poll Generation ---
    sample_transcript = "The team discussed the deadline for the project. Alice proposed extending it by two weeks. Bob argued for adding more resources instead to meet the original deadline. Carol suggested a compromise, extending by one week and reallocating some tasks. David expressed concerns about budget impacts of adding resources."
    logger.info("\n--- Testing generate_poll_from_transcript ---")
    title, question, options = generate_poll_from_transcript(sample_transcript)
    logger.info(f"Generated Poll:")
    logger.info(f"  Title: {title}")
    logger.info(f"  Question: {question}")
    logger.info(f"  Options: {options}")

    # --- Test Poll Posting ---
    logger.info("\n--- Testing post_poll_to_zoom (requires real token and meeting ID) ---")
    # You would need to set a real token and meeting ID in mock_config above to test this
    # post_success = post_poll_to_zoom(title, question, options, config.get_config("MEETING_ID"), config.get_config("ZOOM_TOKEN"))
    # logger.info(f"Poll post successful: {post_success}")