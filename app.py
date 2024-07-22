#!/usr/bin/env python
# coding: utf-8

# In[6]:


import os
import streamlit as st
import boto3
import tempfile
import json
import botocore
import pandas as pd
import time

# ... (keep all the existing functions)

st.title("AWS Textract with Streamlit - Table Extraction")
st.write("Enter your AWS credentials and upload an image or PDF file to extract tables using AWS Textract.")

# AWS Credentials Input
aws_access_key = st.text_input("AWS Access Key ID", type="password")
aws_secret_key = st.text_input("AWS Secret Access Key", type="password")
aws_region = st.selectbox("AWS Region", ["us-east-2", "us-east-1", "us-west-1", "us-west-2"], index=0)
s3_bucket_name = st.text_input("S3 Bucket Name")

if st.button("Confirm Credentials"):
    if check_aws_credentials(aws_access_key, aws_secret_key, aws_region):
        st.success("AWS credentials are valid!")
        st.session_state.credentials_valid = True
    else:
        st.error("Invalid AWS credentials. Please check and try again.")
        st.session_state.credentials_valid = False

# File Upload (only show if credentials are valid)
if st.session_state.get('credentials_valid', False):
    uploaded_file = st.file_uploader("Choose an image or PDF file", type=["jpg", "jpeg", "png", "pdf"])

    if uploaded_file is not None and 'processed' not in st.session_state:
        temp_file_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as temp_file:
                temp_file.write(uploaded_file.getvalue())
                temp_file_path = temp_file.name
            
            textract_client = boto3.client('textract',
                                           aws_access_key_id=aws_access_key,
                                           aws_secret_access_key=aws_secret_key,
                                           region_name=aws_region)
            
            s3_client = boto3.client('s3',
                                     aws_access_key_id=aws_access_key,
                                     aws_secret_access_key=aws_secret_key,
                                     region_name=aws_region)
            
            with st.spinner("Processing document..."):
                tables, response_json_path, simplified_response = process_document(temp_file_path, textract_client, s3_client, s3_bucket_name)
            
            st.session_state.processed = True
            st.session_state.response_json_path = response_json_path
            st.session_state.simplified_response = simplified_response
            st.session_state.tables = tables

        except botocore.exceptions.ClientError as e:
            st.error(f"AWS Error: {str(e)}")
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
            st.error("Please check the AWS credentials, S3 bucket permissions, and try again.")
        finally:
            # Clean up the temporary files
            if temp_file_path and os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

# Show download button and table extraction results only if processing is complete
if st.session_state.get('processed', False):
    response_json_path = st.session_state.response_json_path
    simplified_response = st.session_state.simplified_response
    tables = st.session_state.tables
    
    # JSON file rename input
    st.subheader("Download Full JSON Response:")
    json_file_name = st.text_input("Enter JSON file name (without .json extension)", value='textract_response')
    
    with open(response_json_path, 'rb') as f:
        st.download_button(
            label="Download JSON",
            data=f,
            file_name=f"{json_file_name}.json" if json_file_name else 'textract_response.json',
            mime='application/json'
        )

    # Now display the extracted information
    st.subheader("Detected Tables:")
    st.write(f"Number of tables detected: {len(tables)}")
    if tables:
        for i, table in enumerate(tables):
            st.write(f"Table {i+1}:")
            if table:
                df = pd.DataFrame(table)
                st.dataframe(df)
            else:
                st.write("Empty table detected")
    else:
        st.write("No tables detected")

    # Debug information
    st.subheader("Debug Information:")
    st.write(f"Number of blocks processed: {len(simplified_response['Blocks'])}")
    st.json(simplified_response)

    # Display structure of the first few blocks
    st.subheader("Structure of First Few Blocks:")
    first_few_blocks = simplified_response['Blocks'][:10]  # Display first 10 blocks
    for i, block in enumerate(first_few_blocks):
        st.write(f"Block {i}:")
        st.json(block)
else:
    st.info("Please enter and confirm your AWS credentials to proceed.")

