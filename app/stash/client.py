import requests


class StashClient:

    def __init__(self, url, api_key):
        self.url = url.rstrip("/")
        self.api_key = api_key
        self.endpoint = f"{self.url}/graphql"


    def query(self, query, variables=None):

        response = requests.post(
            self.endpoint,
            headers={
                "ApiKey": self.api_key,
                "Content-Type": "application/json",
            },
            json={
                "query": query,
                "variables": variables or {}
            },
            timeout=30
        )


        result = response.json()

        if "errors" in result:
            print("GRAPHQL ERRORS:")
            print(result["errors"])
            raise Exception(result["errors"])

        response.raise_for_status()

        return result["data"]


    def get_performers(self):

        query = """
        query {
          findPerformers(
            filter:{
              per_page:1000
            }
          ){
            performers{
              id
              name
              urls
            }
          }
        }
        """

        data = self.query(query)

        return data["findPerformers"]["performers"]

    def scan_path(self, path):

        query = """
        mutation MetadataScan($input: ScanMetadataInput!) {
          metadataScan(input: $input)
        }
        """

        data = self.query(
            query,
            {
                "input": {
                    "paths": [
                        path
                    ]
                }
            }
        )

        return data["metadataScan"]
