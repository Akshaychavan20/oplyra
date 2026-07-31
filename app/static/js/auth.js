// Auth Helper Interactions - Oplyra

document.addEventListener('DOMContentLoaded', function() {
    
    // 1. Password Visibility Toggle
    const togglePasswordBtns = document.querySelectorAll('.toggle-password-btn');
    togglePasswordBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            const inputId = this.getAttribute('data-target');
            const passwordInput = document.getElementById(inputId);
            
            if (passwordInput) {
                if (passwordInput.type === 'password') {
                    passwordInput.type = 'text';
                    this.innerHTML = '<i class="bi bi-eye-slash"></i>';
                } else {
                    passwordInput.type = 'password';
                    this.innerHTML = '<i class="bi bi-eye"></i>';
                }
            }
        });
    });

    // 2. Real-time Password Matching Validation
    const password = document.getElementById('password');
    const confirmPassword = document.getElementById('confirm_password');
    const matchMessage = document.getElementById('password-match-msg');
    const registerForm = document.getElementById('register-form');

    if (password && confirmPassword && matchMessage) {
        function checkPasswordMatch() {
            if (confirmPassword.value.length === 0) {
                matchMessage.textContent = '';
                confirmPassword.classList.remove('is-valid', 'is-invalid');
                return;
            }

            if (password.value === confirmPassword.value) {
                matchMessage.textContent = 'Passwords match';
                matchMessage.className = 'text-success small mt-1';
                confirmPassword.classList.remove('is-invalid');
                confirmPassword.classList.add('is-valid');
            } else {
                matchMessage.textContent = 'Passwords do not match';
                matchMessage.className = 'text-danger small mt-1';
                confirmPassword.classList.remove('is-valid');
                confirmPassword.classList.add('is-invalid');
            }
        }

        password.addEventListener('input', checkPasswordMatch);
        confirmPassword.addEventListener('input', checkPasswordMatch);
        
        if (registerForm) {
            registerForm.addEventListener('submit', function(e) {
                if (password.value !== confirmPassword.value) {
                    e.preventDefault();
                    confirmPassword.classList.add('is-invalid');
                    matchMessage.textContent = 'Please make sure passwords match before submitting.';
                    matchMessage.className = 'text-danger small mt-1';
                }
            });
        }
    }

    // 3. Auto-fade Flash alerts
    const alerts = document.querySelectorAll('.alert-custom');
    alerts.forEach(alert => {
        setTimeout(() => {
            // Apply fade-out animation styles
            alert.style.transition = 'transform 0.4s ease, opacity 0.4s ease';
            alert.style.transform = 'translateX(120%)';
            alert.style.opacity = '0';
            
            // Remove from DOM after transition completes
            setTimeout(() => {
                alert.remove();
            }, 400);
        }, 5000); // Wait 5 seconds
    });
});
