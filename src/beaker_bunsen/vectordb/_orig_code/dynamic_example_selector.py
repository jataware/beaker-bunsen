# -*- coding: utf-8 -*-
import os
import chromadb
import openai
import json
def start_chromadb(docker=False,collection_name="examples",path="/bio_context/chromadb_functions"):

    if docker:
        #Initialize ChromaDB client and create a collection
        client = chromadb.HttpClient(host='localhost', port=8000)
    else:
        chroma_client = chromadb.PersistentClient(path=path)
    
    collection = chroma_client.get_or_create_collection(name=collection_name)
    
    openai.api_key = os.environ['OPENAI_API_KEY']
    return collection
#TODO: change example format to the same as what the agent will see?
#TODO: change examples to conversations?
#TODO: change search to look for code similar to the code in the current notebook? (requires openai embeddings..)
def add_examples(json_files:list=['mira_manual_examples.json']):
    user_queries_or_descriptions=[]
    code_strings=[]
    metadatas=[]
    for file in json_files:
        examples=json.load(open(file,'r'))
        for example in examples:
            user_queries_or_descriptions.append(example['description'])
            code_strings.append(example['code'])
            metadatas.append({'origination_method':example['origination_method'],
                              'origination_source':example['origination_source'],
                              'origination_source_type':example['origination_source_type']})
    #TODO: add check for existing docs..
    u_query_collection=start_chromadb(collection_name="user_queries",path="./chromadb_functions")
    u_query_collection.add(
        documents=['Request: ' + query for query in user_queries_or_descriptions],
        metadatas=metadatas, #TODO: maybe add functions or classes in the code examples for easier lookup?
        ids=[str(i) for i in range(len(user_queries_or_descriptions))] #TODO: make more descriptive?
    )
    #separate index for user queries then just use sim search on query?
    examples_collection=start_chromadb(collection_name="examples",path="./chromadb_functions")
    examples_collection.add(
        documents=code_strings, #add back Code: ?
        metadatas=metadatas, #TODO: maybe add functions or classes in the code examples for easier lookup?
        ids=[str(i) for i in range(len(code_strings))] #make more descriptive?
    )
    
def query_examples(query, n_results=5):
    u_query_collection=start_chromadb(collection_name="user_queries")
    examples_collection=start_chromadb(collection_name="examples")
    results=u_query_collection.query(query_texts=[query],
                    n_results=n_results)
    examples_ids=results['ids'][0] 
    examples=examples_collection.get(ids=examples_ids)['documents']
    
    return examples

def convert_manual_examples_to_new_examples_format(manual_examples:list):
    manual_examples_json=[]
    for item in manual_examples:
        code = item[1].replace('Code:','').lstrip()
        if not code.startswith('```') :code='```'+code
        if not code.endswith('```'):code=code+'```'
        manual_examples_json.append({'origination_source_type':'code_file',
                          'origination_source':'custom_library',
                          'origination_method':'extract_from_library_manual',
                          'code':code, 
                          'description':item[0]})
        
    json.dump(manual_examples_json,open(f'manual_examples.json','w'))
    return manual_examples_json



