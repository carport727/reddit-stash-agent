from app.stash.client import stash_request


def find_performer(name):

    query = """
    query FindPerformer($filter: FindFilterType!) {
        findPerformers(filter:$filter) {
            performers {
                id
                name
            }
        }
    }
    """

    variables = {
        "filter": {
            "q": name
        }
    }


    result = stash_request(
        query,
        variables
    )


    performers = result["data"]["findPerformers"]["performers"]

    for performer in performers:

        if performer["name"].lower() == name.lower():
            return performer["id"]


    return None



def create_performer(name):

    mutation = """
    mutation($input: PerformerCreateInput!) {
        performerCreate(input:$input) {
            id
        }
    }
    """

    variables = {
        "input": {
            "name": name
        }
    }


    result = stash_request(
        mutation,
        variables
    )


    return result["data"]["performerCreate"]["id"]



def get_or_create_performer(name):

    performer_id = find_performer(name)


    if performer_id:
        return performer_id


    return create_performer(name)
