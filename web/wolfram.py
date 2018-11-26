import wolframalpha

client = wolframalpha.Client("JGH5WQ-TUAEV87672")

def get_answer(question):
    res = client.query(question)
    return(next(res.results).text)
