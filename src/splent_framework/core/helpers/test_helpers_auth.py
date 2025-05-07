def login(test_client, email, password):
    response = test_client.post(
        "/login",
        data=dict(email=email, password=password),
        follow_redirects=True,
    )
    return response

def logout(test_client):
    return test_client.get("/logout", follow_redirects=True)
