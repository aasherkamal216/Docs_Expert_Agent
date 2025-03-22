# main.py
import chainlit as cl
from agent import make_graph

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import AIMessageChunk, HumanMessage

from chainlit.input_widget import Select, Slider

import os, uuid, base64
from dotenv import load_dotenv

_ : bool = load_dotenv()

#################################
# Quick Starter Questions
#################################
@cl.set_starters
async def set_starters():
    return [
        cl.Starter(
            label="LangGraph Chatbot Creation",
            message="Create a chatbot in LangGraph. Give it web access using tavily tool.",
            icon="/public/msg_icons/chatbot.png",
            ),

        cl.Starter(
            label="Explain MCP",
            message="Explain Model Context Protocol (MCP) to a non-tech person.",
            icon="/public/msg_icons/usb.png",
            ),
        cl.Starter(
            label="Composio Tools Integration",
            message="How can I connect Composio tools to my agent built with LangGraph?",
            icon="/public/msg_icons/tools.png",
            ),

        ]
#################################
# Encoding Images 
#################################
async def process_image(image: cl.Image):
    """
    Processes an image file, reads its data, and converts it to a base64 encoded string.
    """
    try:
        with open(image.path, "rb") as image_file:
            image_data = image_file.read()
        base64_image = base64.b64encode(image_data).decode("utf-8")
        return {
            "type": "image_url",
            "image_url": {
                "url": f"data:image/{image.mime.split('/')[-1]};base64,{base64_image}"
            }
        }
    except Exception as e:
        print(f"Error reading image file: {e}")
        return {"type": "text", "text": f"Error processing image {image.name}."}

#################################
# Chat Settings
#################################
@cl.on_chat_start
async def on_chat_start():
    thread_id = f"thread-{uuid.uuid4()}"
    # Store thread ID in session
    cl.user_session.set("thread_id", thread_id)

    # Get model settings from user
    settings = await cl.ChatSettings(
        [
            Select(
                id="model",
                label="Gemini - Model",
                values=["gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-2.0-pro-exp"],
                initial_index=0,
            ),
            Slider(
                id="temperature",
                label="Temperature",
                initial=1,
                min=0,
                max=2,
                step=0.1,
            ),
        ]
    ).send()

    # Create model with given settings
    model = ChatGoogleGenerativeAI(
        model=settings["model"], 
        api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=settings["temperature"]
        )

    # Store model in session
    cl.user_session.set("model", model)

#################################
# Processing Messages
#################################
@cl.on_message
async def on_message(message: cl.Message):
    thread_id = cl.user_session.get("thread_id")  # Retrieve the user-specific thread ID

    # Get model & config from session
    model = cl.user_session.get("model", "gemini-2.0-flash")
    config = {"configurable": {"thread_id": thread_id}}

    # Prepare the content list for the current message
    content = []

    # Add text content
    if message.content:
        content.append({"type": "text", "text": message.content})
    
    # Process image files
    image_elements = [element for element in message.elements if "image" in element.mime]
    for image in image_elements:
        if image.path:
            content.append(await process_image(image))
        else:
            print(f"Image {image.name} has no content and no path.")
            content.append({"type": "text", "text": f"Image {image.name} could not be processed."})
    
    msg = cl.Message(content="")  # Initialize an empty message for streaming

    try:
        async with make_graph(model) as agent:
            async for stream, metadata in agent.astream(
                {"messages": HumanMessage(content=content)}, 
                config=config, 
                stream_mode="messages"
                ):

                if isinstance(stream, AIMessageChunk) and stream.content:   
                    await msg.stream_token(stream.content.replace("```", "\n```"))
            await msg.send()

    except Exception as e:
        await cl.Message(content=f"Error during agent invocation: {e}").send()
