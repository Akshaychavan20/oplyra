// AI Content Generation UI Helpers - Oplyra

document.addEventListener('DOMContentLoaded', function() {
    
    // 1. Dynamic Form Fields Toggle depending on Content Format
    const contentTypeSelect = document.getElementById('type');
    const topicContainer = document.getElementById('topic-container');
    const topicLabel = document.getElementById('topic-label');
    const topicInput = document.getElementById('topic');
    const productContainer = document.getElementById('product-container');
    const productNameInput = document.getElementById('product_name');

    if (contentTypeSelect) {
        function adjustFormFields() {
            const format = contentTypeSelect.value;
            
            if (format === 'blog') {
                // Blog Mode: Topic is required, Product Name is optional
                topicContainer.classList.remove('d-none');
                topicLabel.textContent = 'Blog Topic / Title *';
                topicInput.required = true;
                topicInput.placeholder = 'e.g., Top 5 High-FPS Gaming Laptops in 2026';
                
                productContainer.classList.remove('d-none');
                productNameInput.required = false;
                productNameInput.placeholder = 'e.g., ASUS ROG Zephyrus (Optional)';
            } 
            else if (format === 'email') {
                // Email Mode: Product Name is required, Topic is optional
                topicContainer.classList.remove('d-none');
                topicLabel.textContent = 'Email Focus / Theme (Optional)';
                topicInput.required = false;
                topicInput.placeholder = 'e.g., Summer clearance sale discount promo';
                
                productContainer.classList.remove('d-none');
                productNameInput.required = true;
                productNameInput.placeholder = 'e.g., Smart Blender Pro';
            } 
            else if (format === 'facebook_post') {
                // FB Post Mode: Product Name is required, Topic is optional
                topicContainer.classList.remove('d-none');
                topicLabel.textContent = 'Campaign Focus / Message (Optional)';
                topicInput.required = false;
                topicInput.placeholder = 'e.g., Promoting key wireless features';
                
                productContainer.classList.remove('d-none');
                productNameInput.required = true;
                productNameInput.placeholder = 'e.g., Noise-Cancelling Headphones';
            } 
            else if (format === 'product_review') {
                // Product Review Mode: Product Name is required, Topic is not needed
                topicContainer.classList.add('d-none');
                topicInput.required = false;
                
                productContainer.classList.remove('d-none');
                productNameInput.required = true;
                productNameInput.placeholder = 'e.g., Mechanical Gaming Keyboard Redux';
            }
            else if (format === 'carousel') {
                topicContainer.classList.remove('d-none');
                topicLabel.textContent = 'Carousel Topic / Focus (Optional)';
                topicInput.required = false;
                topicInput.placeholder = 'e.g., 5 critical copywriting tips for higher conversions';
                
                productContainer.classList.remove('d-none');
                productNameInput.required = true;
                productNameInput.placeholder = 'e.g., Copywriting Masterclass';
            }
            else if (format === 'video_script') {
                topicContainer.classList.remove('d-none');
                topicLabel.textContent = 'Video Script Topic / Theme (Optional)';
                topicInput.required = false;
                topicInput.placeholder = 'e.g., Showing how to set up the smart light in 3 steps';
                
                productContainer.classList.remove('d-none');
                productNameInput.required = true;
                productNameInput.placeholder = 'e.g., Smart Ambient Light';
            }
            else if (format === 'image_prompt') {
                topicContainer.classList.remove('d-none');
                topicLabel.textContent = 'Composition Context / Details (Optional)';
                topicInput.required = false;
                topicInput.placeholder = 'e.g., Cyberpunk street at night, neon reflections, rain';
                
                productContainer.classList.remove('d-none');
                productNameInput.required = true;
                productNameInput.placeholder = 'e.g., Futuristic Cyborg Warrior';
            }
            else if (format === 'ad_copy') {
                topicContainer.classList.remove('d-none');
                topicLabel.textContent = 'Ad Campaign Theme / Focus (Optional)';
                topicInput.required = false;
                topicInput.placeholder = 'e.g., Free shipping and 20% discount code';
                
                productContainer.classList.remove('d-none');
                productNameInput.required = true;
                productNameInput.placeholder = 'e.g., Eco-Friendly Travel Backpack';
            }
        }
        
        contentTypeSelect.addEventListener('change', adjustFormFields);
        adjustFormFields(); // Initialize state on page load
    }

    // 2. AJAX Form Submission and Fullscreen Spinner Loader
    const generateForm = document.getElementById('generate-form');
    const loadingOverlay = document.getElementById('loading-overlay');
    const errorAlertContainer = document.getElementById('error-alert-container');

    if (generateForm && loadingOverlay) {
        generateForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            // Check form validity with Bootstrap validation state
            if (!generateForm.checkValidity()) {
                e.stopPropagation();
                generateForm.classList.add('was-validated');
                return;
            }
            
            // Clear past errors
            if (errorAlertContainer) {
                errorAlertContainer.classList.add('d-none');
                errorAlertContainer.textContent = '';
            }

            // Display loading overlay spinner
            loadingOverlay.classList.remove('d-none');
            
            // Form Data extraction (API keys are server-side only — never from browser storage)
            const formData = new FormData(generateForm);
            const csrfMeta = document.querySelector('meta[name="csrf-token"]');
            const csrfToken = csrfMeta ? csrfMeta.getAttribute('content') : '';
            if (csrfToken && !formData.get('csrf_token')) {
                formData.append('csrf_token', csrfToken);
            }

            fetch('/content/generate', {
                method: 'POST',
                headers: csrfToken ? { 'X-CSRF-Token': csrfToken } : {},
                body: formData
            })
            .then(async response => {
                let data;
                try {
                    data = await response.json();
                } catch (parseErr) {
                    throw new Error('Server returned an invalid response. Please refresh and try again.');
                }
                return { status: response.status, body: data };
            })
            .then(result => {
                if (result.status === 200 && result.body.success) {
                    // Redirect to view preview page on success
                    window.location.href = result.body.redirect_url;
                } else {
                    // Hide spinner loader
                    loadingOverlay.classList.add('d-none');
                    
                    // Display error banner
                    const errMsg = result.body.error || "An unexpected error occurred during copy generation.";
                    if (errorAlertContainer) {
                        errorAlertContainer.classList.remove('d-none');
                        errorAlertContainer.innerHTML = `<i class="bi bi-exclamation-triangle-fill me-2"></i>${errMsg}`;
                        
                        // Scroll back to error banner
                        errorAlertContainer.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    } else {
                        alert(errMsg);
                    }
                }
            })
            .catch(err => {
                loadingOverlay.classList.add('d-none');
                console.error("Fetch Generation Error:", err);
                const errMsg = err.message || "Network connection error occurred. Please try again.";
                if (errorAlertContainer) {
                    errorAlertContainer.classList.remove('d-none');
                    errorAlertContainer.innerHTML = `<i class="bi bi-exclamation-triangle-fill me-2"></i>${errMsg}`;
                }
            });
        });
    }

    // 3. Clipboard Copy Utility
    const copyBtn = document.getElementById('copy-btn');
    const copyTarget = document.getElementById('copy-target');

    if (copyBtn && copyTarget) {
        copyBtn.addEventListener('click', function() {
            // Get raw text (inner text, preserving newlines)
            const textToCopy = copyTarget.innerText || copyTarget.textContent;
            
            navigator.clipboard.writeText(textToCopy)
            .then(() => {
                // Update copy button icon states to checkmark
                const originalHTML = copyBtn.innerHTML;
                copyBtn.innerHTML = '<i class="bi bi-check2-all me-1"></i>Copied!';
                copyBtn.classList.remove('btn-secondary-custom');
                copyBtn.classList.add('btn-success');
                
                // Reset states after 2 seconds
                setTimeout(() => {
                    copyBtn.innerHTML = originalHTML;
                    copyBtn.classList.add('btn-secondary-custom');
                    copyBtn.classList.remove('btn-success');
                }, 2000);
            })
            .catch(err => {
                console.error("Failed to copy asset copy to clipboard:", err);
                alert("Failed to copy content to clipboard.");
            });
        });
    }

    // 4. AJAX Content Regeneration and Fullscreen Spinner Loader
    const regenerateBtn = document.getElementById('regenerate-btn');
    if (regenerateBtn && loadingOverlay) {
        regenerateBtn.addEventListener('click', function(e) {
            e.preventDefault();
            const contentId = this.getAttribute('data-content-id');
            if (!contentId) return;

            if (!confirm('Are you sure you want to regenerate this content? The current draft will be overwritten.')) {
                return;
            }

            // Display loading overlay spinner
            loadingOverlay.classList.remove('d-none');

            // Fetch CSRF token from meta tag (guard against missing tag)
            const csrfMeta = document.querySelector('meta[name="csrf-token"]');
            const csrfToken = csrfMeta ? csrfMeta.getAttribute('content') : '';
            
            const params = new URLSearchParams({
                'csrf_token': csrfToken
            });

            const headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-CSRF-Token': csrfToken
            };

            fetch(`/content/regenerate/${contentId}`, {
                method: 'POST',
                headers: headers,
                body: params
            })
            .then(response => response.json().then(data => ({ status: response.status, body: data })))
            .then(result => {
                if (result.status === 200 && result.body.success) {
                    // Redirect to view preview page on success
                    window.location.href = result.body.redirect_url;
                } else {
                    // Hide spinner loader
                    loadingOverlay.classList.add('d-none');
                    const errMsg = result.body.error || "An unexpected error occurred during copy regeneration.";
                    alert(errMsg);
                }
            })
            .catch(err => {
                loadingOverlay.classList.add('d-none');
                console.error("Fetch Regeneration Error:", err);
                alert("Network connection error occurred. Please try again.");
            });
        });
    }
});
