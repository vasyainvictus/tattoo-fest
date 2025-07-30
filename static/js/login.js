// static/js/login.js
document.getElementById('login-form').addEventListener('submit', function(e) {
    const code = document.getElementById('code').value;
    if (!/^\d{6}$/.test(code)) {
        e.preventDefault();
        alert('Код должен состоять из 6 цифр!');
    }
});