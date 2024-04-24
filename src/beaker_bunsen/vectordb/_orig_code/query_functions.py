import chromadb
import os
import openai

def start_chromadb(docker=False):
    import chromadb
    if docker:
        #Initialize ChromaDB client and create a collection
        client = chromadb.HttpClient(host='localhost', port=8000)
    else:
        #chroma_client = chromadb.PersistentClient(path="./chromabd_functions")
        chroma_client = chromadb.PersistentClient(path="/bio_context/chromadb_functions")
    
    collection = chroma_client.get_or_create_collection(name="full")
    
    openai.api_key = os.environ['OPENAI_API_KEY']
    return collection

def query_functions(query, n_results=10):
    '''
    Takes in a query and returns the top n results in the following form:

    {'function_name': {
                        'description': 'description of the function here',
                        'docstring': 'the docstring of the function here'
                        },
    ...
    }
    '''
    collection=start_chromadb(docker=False)
    result = collection.query(
        query_texts=[query],
        n_results=n_results
    )
    cleaned_results = {}
    for i in range(len(result['ids'][0])):
        func = result['ids'][0][i]
        description = result['documents'][0][i]
        docstring = result['metadatas'][0][i]['docstring']
        source_code = result['metadatas'][0][i]['source_code']
        cleaned_results[func] = {'description': description, 'docstring': docstring, 'source_code': source_code}

    return cleaned_results

#query_functions("{{query}}")