"""
Basic Streamlit Web UI for interacting with the MCPEnhancedAgent and MCP Servers.
"""

import streamlit as st
import sys
import os
import asyncio
import logging

# Add project root to allow importing agent
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.mcp_enhanced_agent import MCPEnhancedAgent

# --- App Configuration ---
st.set_page_config(layout="wide", page_title="MCP Agent UI")
st.title("MCP Agent Interface")

# --- Initialization (Run Once) ---
# Use Streamlit's session state to store the agent instance
if 'agent' not in st.session_state:
    st.session_state.agent = None # Initialize as None

# --- Main App Logic ---

# Sidebar for configuration
st.sidebar.header("Configuration")
code_server_url = st.sidebar.text_input("Code Server URL", os.environ.get("MCP_CODE_SERVER_URL", "http://localhost:8000"))
test_server_url = st.sidebar.text_input("Test Server URL", os.environ.get("MCP_TEST_SERVER_URL", "http://localhost:8082"))
api_key = st.sidebar.text_input("API Key", os.environ.get("MCP_API_KEY", "dev_secret_key"), type="password")

# Button to initialize/re-initialize agent
if st.sidebar.button("Connect Agent"):
    try:
        # We need to manually override env vars if provided in UI
        os.environ['MCP_CODE_SERVER_URL'] = code_server_url
        os.environ['MCP_TEST_SERVER_URL'] = test_server_url
        os.environ['MCP_API_KEY'] = api_key
        
        # Instantiate the agent (ensure env vars are read by agent)
        st.session_state.agent = MCPEnhancedAgent(
            # Pass URLs/key directly if agent init supports it,
            # otherwise rely on environment variables set above.
        )
        st.sidebar.success("Agent Connected!")
        # Optional: Add connection check here
        # asyncio.run(st.session_state.agent.code_client.check_connection())
        # asyncio.run(st.session_state.agent.test_client.check_connection())
        # st.sidebar.info("Server connections verified.")
    except Exception as e:
        st.sidebar.error(f"Agent connection failed: {e}")
        st.session_state.agent = None

# Check if agent is connected
if st.session_state.agent is None:
    st.warning("Agent not connected. Please configure and click 'Connect Agent' in the sidebar.")
    st.stop() # Stop execution if agent isn't ready

# --- UI Sections ---

# Code Analysis Section
st.header("Code Operations")
code_col1, code_col2 = st.columns(2)

with code_col1:
    st.subheader("Input Code")
    code_input = st.text_area("Enter Python code here", height=300, key="code_input")
    analyze_button = st.button("Analyze Code")
    format_button = st.button("Format Code")
    fix_button = st.button("Fix Code")

with code_col2:
    st.subheader("Results")
    results_placeholder = st.empty() # Placeholder for results
    results_placeholder.info("Results will appear here...")

# Test Runner Section
st.header("Test Runner")
test_col1, test_col2 = st.columns(2)

with test_col1:
    st.subheader("Configuration")
    project_path = st.text_input("Project Path (Absolute)", os.getcwd())
    test_path = st.text_input("Test Path (Relative to Project)", "tests")
    test_runner = st.selectbox("Test Runner", ["pytest", "unittest", "nose2"])
    
    # Execution Mode Selection
    exec_mode = st.radio("Execution Mode", ["local", "docker"], horizontal=True)
    
    docker_image = "python:3.11-slim" # Default
    if exec_mode == "docker":
        docker_image = st.text_input("Docker Image", docker_image)
        st.caption("Ensure Docker is running locally.")
        
    # TODO: Add more config options like timeout, max_failures?
    
    run_tests_button = st.button("Run Tests")

with test_col2:
    st.subheader("Test Output")
    test_output_placeholder = st.empty()
    test_output_placeholder.info("Test output will appear here...")

# --- Button Actions (using asyncio for agent calls) ---

async def run_analyze():
    if code_input:
        with st.spinner("Analyzing code..."):
            results_placeholder.empty() # Clear previous results
            result = await st.session_state.agent.analyze_code(code_input)
            if result.get("success"):
                results_placeholder.success("Analysis complete.")
                st.json(result.get("analysis", []))
            else:
                results_placeholder.error(f"Analysis failed: {result.get('message')}")
                st.code(result.get("details", ""), language='text')
    else:
        st.warning("Please enter code to analyze.")

async def run_format():
    if code_input:
        with st.spinner("Formatting code..."):
            results_placeholder.empty()
            result = await st.session_state.agent.format_code(code_input)
            if result.get("success"):
                results_placeholder.success("Formatting complete.")
                # Update the input area with formatted code
                st.session_state.code_input = result.get("formatted_code", code_input)
                st.rerun() # Rerun to update the text_area value
            else:
                results_placeholder.error(f"Formatting failed: {result.get('message')}")
                st.code(result.get("details", ""), language='text')
    else:
        st.warning("Please enter code to format.")

async def run_fix():
    if code_input:
        with st.spinner("Attempting to fix code..."):
            results_placeholder.empty()
            result = await st.session_state.agent.fix_code(code_input)
            if result.get("success"):
                results_placeholder.success("Fix attempt complete.")
                # Update the input area with fixed code
                st.session_state.code_input = result.get("fixed_code", code_input)
                st.rerun()
            else:
                results_placeholder.error(f"Fix attempt failed: {result.get('message')}")
                st.code(result.get("details", ""), language='text')
    else:
        st.warning("Please enter code to fix.")

async def run_tests():
    if project_path and test_path:
        with st.spinner(f"Running {test_runner} tests in {exec_mode} mode..."):
            test_output_placeholder.empty() # Clear previous output
            output_lines = []
            
            try:
                stream = st.session_state.agent.run_tests(
                    project_path=project_path,
                    test_path=test_path,
                    runner=test_runner,
                    mode=exec_mode, 
                    docker_image=docker_image if exec_mode == "docker" else None
                )
                
                # Process and display the stream line by line
                output_area = test_output_placeholder.container()
                async for line in stream:
                    output_lines.append(line) # Store raw line
                    line_stripped = line.strip()
                    
                    # Wrap condition in parentheses to allow multi-line without \
                    if (line_stripped.startswith("--- ERROR") or 
                        line_stripped.startswith("--- SERVER ERROR") or 
                        line_stripped.startswith("--- STREAM PROCESSING ERROR") or 
                        line_stripped.startswith("--- UNEXPECTED")):
                        output_area.error(line_stripped)
                    elif line_stripped.startswith("--- "):
                        # Display status lines prominently
                        output_area.info(line_stripped)
                    elif line_stripped.startswith("STDOUT: "):
                        output_area.code(line_stripped[8:], language='text')
                    elif line_stripped.startswith("STDERR: "):
                        # Use markdown for slight emphasis on stderr
                        output_area.warning(f"`{line_stripped[8:]}`") 
                    else:
                        # Default display for other lines
                        output_area.text(line)
                
                st.success("Test stream finished.")
                
                # Optional: Add button to fetch full results from DB if ID was captured
                # result_id = extract_id_from_lines(output_lines)
                # if result_id and st.button("Fetch Full Result Details"): 
                #    ... fetch result from server ...

            except Exception as e:
                st.error(f"Error running tests or processing stream: {e}")
                logging.exception("UI Error running tests:") 
    else:
        st.warning("Please enter Project Path and Test Path.")

# Assign async functions to button clicks
if analyze_button:
    asyncio.run(run_analyze())

if format_button:
    asyncio.run(run_format())

if fix_button:
    asyncio.run(run_fix())

if run_tests_button:
    asyncio.run(run_tests())

# Add footer or other info
st.sidebar.markdown("---")
st.sidebar.info("Connect agent to enable operations.") 