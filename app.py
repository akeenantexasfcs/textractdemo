#!/usr/bin/env python
# coding: utf-8

# In[6]:


import os
import streamlit as st
import boto3
import tempfile
import json
import botocore

def check_aws_credentials(access_key, secret_key, region):
    try:
        session = boto3.Session(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region
        )
        sts = session.client('sts')
        sts.get_caller_identity()
        return True
    except botocore.exceptions.ClientError:
        return False

def extract_text_from_image(image_path, textract_client):
    with open(image_path, 'rb') as document:
        image_bytes = document.read()
    
    response = textract_client.detect_document_text(Document={'Bytes': image_bytes})
    
    # Save the response as a JSON file
    response_json_path = image_path + '.json'
    with open(response_json_path, 'w') as json_file:
        json.dump(response, json_file, indent=4)
    
    # Extract text from response
    extracted_text = ""
    for item in response['Blocks']:
        if item['BlockType'] == 'LINE':
            extracted_text += item['Text'] + "\n"
    
    return extracted_text, response_json_path

st.title("AWS Textract with Streamlit v3")
st.write("Enter your AWS credentials and upload an image to extract text using AWS Textract.")

# AWS Credentials Input
aws_access_key = st.text_input("AWS Access Key ID", type="password")
aws_secret_key = st.text_input("AWS Secret Access Key", type="password")
aws_region = st.selectbox("AWS Region", ["us-east-2", "us-east-1", "us-west-1", "us-west-2"], index=0)

if st.button("Confirm Credentials"):
    if check_aws_credentials(aws_access_key, aws_secret_key, aws_region):
        st.success("AWS credentials are valid!")
        st.session_state.credentials_valid = True
    else:
        st.error("Invalid AWS credentials. Please check and try again.")
        st.session_state.credentials_valid = False

# File Upload (only show if credentials are valid)
if st.session_state.get('credentials_valid', False):
    uploaded_file = st.file_uploader("Choose an image file", type=["jpg", "jpeg", "png", "pdf"])

    if uploaded_file is not None:
        temp_file_path = None
        response_json_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(uploaded_file.getvalue())
                temp_file_path = temp_file.name
            
            textract_client = boto3.client('textract',
                                           aws_access_key_id=aws_access_key,
                                           aws_secret_access_key=aws_secret_key,
                                           region_name=aws_region)
            
            extracted_text, response_json_path = extract_text_from_image(temp_file_path, textract_client)
            st.write("Extracted Text:")
            st.text(extracted_text)
            
            st.write("Download JSON Response:")
            with open(response_json_path, 'rb') as f:
                st.download_button(
                    label="Download JSON",
                    data=f,
                    file_name='textract_response.json',
                    mime='application/json'
                )
        except botocore.exceptions.ClientError as e:
            st.error(f"AWS Error: {str(e)}")
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
        finally:
            # Clean up the temporary files
            if temp_file_path and os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
            if response_json_path and os.path.exists(response_json_path):
                os.unlink(response_json_path)
else:
    st.info("Please enter and confirm your AWS credentials to proceed.")

