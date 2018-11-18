import wolframalpha

client = wolframalpha.Client("JGH5WQ-TUAEV87672")

def get_answer(question):
    res = client.query(question)
    print(next(res.results).text)
