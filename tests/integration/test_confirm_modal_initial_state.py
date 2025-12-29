def test_confirm_modal_hidden_on_dashboard_initial_load(client, db_session, authenticated_client):
    """Fetch the dashboard page as a logged-in user and assert the confirm modal is not visible on initial render.

    We check the modal element exists in the HTML, but does not have the `active` class and has `aria-hidden="true"`.
    """
    # `authenticated_client` fixture provides an authenticated client
    resp = authenticated_client.get('/home')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)

    # Confirm modal markup exists
    assert '<div id="confirmModal"' in html

    # The confirm modal should not be active by default (no active class, aria-hidden="true")
    assert 'class="confirm-modal active"' not in html
    assert 'aria-hidden="false"' not in html
    # The default attribute should indicate hidden state
    assert 'aria-hidden="true"' in html
