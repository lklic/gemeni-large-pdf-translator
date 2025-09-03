document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const browseBtn = document.querySelector('.browse-btn');
    const progressContainer = document.getElementById('progress-container');
    const progressBar = document.getElementById('progress-bar');
    const progressPercentage = document.querySelector('.progress-percentage');
    const fileList = document.getElementById('file-list');
    const filesCount = document.getElementById('files-count');
    const emptyState = document.getElementById('empty-state');
    const modal = document.getElementById('modal');
    const modalContent = document.getElementById('markdown-content');
    const closeButton = document.querySelector('.close-button');
    const toastContainer = document.getElementById('toast-container');

    let progressInterval;

    // Initialize
    fetchFiles();

    // Event Listeners
    dropZone.addEventListener('click', () => fileInput.click());
    browseBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        fileInput.click();
    });

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });

    dropZone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFileUpload(files[0]);
        }
    });

    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            handleFileUpload(fileInput.files[0]);
        }
    });

    closeButton.addEventListener('click', () => {
        modal.style.display = 'none';
    });

    window.addEventListener('click', (event) => {
        if (event.target === modal) {
            modal.style.display = 'none';
        }
    });

    // File Upload Handler
    function handleFileUpload(file) {
        // Validate file type
        if (!file.name.toLowerCase().endsWith('.pdf')) {
            showToast('Please select a PDF file', 'error');
            return;
        }

        // Validate file size (50MB limit)
        const maxSize = 50 * 1024 * 1024; // 50MB
        if (file.size > maxSize) {
            showToast('File size must be less than 50MB', 'error');
            return;
        }

        const formData = new FormData();
        formData.append('file', file);

        // Show upload progress
        showToast(`Uploading ${file.name}...`, 'info');

        fetch('/upload', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                showToast('Upload Error: ' + data.error, 'error');
            } else {
                showToast('Upload successful! Translation started.', 'success');
                progressContainer.style.display = 'block';
                progressBar.style.width = '0%';
                progressPercentage.textContent = '0%';
                startPolling(data.filename);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showToast('An error occurred during upload.', 'error');
        });

        // Reset file input
        fileInput.value = '';
    }

    // Progress Polling
    function startPolling(filename) {
        progressInterval = setInterval(() => {
            fetch(`/progress/${filename}`)
                .then(response => response.json())
                .then(data => {
                    if (data.percentage >= 0) {
                        progressBar.style.width = data.percentage + '%';
                        progressPercentage.textContent = data.percentage + '%';
                    }
                    
                    if (data.percentage >= 100) {
                        clearInterval(progressInterval);
                        showToast('Translation completed successfully!', 'success');
                        setTimeout(() => {
                            progressContainer.style.display = 'none';
                        }, 2000);
                        fetchFiles();
                    } else if (data.percentage < 0) {
                        clearInterval(progressInterval);
                        showToast('Translation failed. Please try again.', 'error');
                        progressContainer.style.display = 'none';
                    }
                })
                .catch(error => {
                    console.error('Progress polling error:', error);
                    clearInterval(progressInterval);
                    showToast('Error checking translation progress', 'error');
                    progressContainer.style.display = 'none';
                });
        }, 2000);
    }

    // Fetch Files
    function fetchFiles() {
        fetch('/files')
            .then(response => response.json())
            .then(files => {
                updateFilesList(files);
                updateFilesCount(files.length);
            })
            .catch(error => {
                console.error('Error fetching files:', error);
                showToast('Error loading files', 'error');
            });
    }

    // Update Files List
    function updateFilesList(files) {
        if (files.length === 0) {
            emptyState.style.display = 'block';
            fileList.style.display = 'none';
        } else {
            emptyState.style.display = 'none';
            fileList.style.display = 'block';
            fileList.innerHTML = '';

            files.forEach(file => {
                const fileItem = createFileItem(file);
                fileList.appendChild(fileItem);
            });
        }
    }

    // Create File Item
    function createFileItem(file) {
        const div = document.createElement('div');
        div.className = 'file-item';
        div.innerHTML = `
            <div class="file-info">
                <div class="file-name">
                    <i class="fas fa-file-pdf"></i>
                    ${file.name}
                </div>
                <div class="file-meta">
                    <div class="file-timestamp">
                        <i class="fas fa-clock"></i>
                        ${file.timestamp}
                    </div>
                    <div class="file-cost" id="cost-${file.name}">
                        <i class="fas fa-dollar-sign"></i>
                        <span class="cost-loading">Loading...</span>
                    </div>
                </div>
            </div>
            <div class="file-actions">
                <button class="action-btn view-btn" data-filename="${file.name}">
                    <i class="fas fa-eye"></i>
                    View
                </button>
                <button class="action-btn cost-btn" data-filename="${file.name}">
                    <i class="fas fa-chart-line"></i>
                    Cost
                </button>
                <a href="/original/${file.name}" class="action-btn original-btn" target="_blank">
                    <i class="fas fa-file-pdf"></i>
                    Original PDF
                </a>
                <a href="/download/${file.name}/md" class="action-btn download-btn" download>
                    <i class="fas fa-download"></i>
                    MD
                </a>
                <a href="/download/${file.name}/txt" class="action-btn download-btn" download>
                    <i class="fas fa-download"></i>
                    TXT
                </a>
                <a href="/download/${file.name}/doc" class="action-btn download-btn" download>
                    <i class="fas fa-download"></i>
                    DOC
                </a>
                <a href="/download/${file.name}/pdf" class="action-btn download-btn" download>
                    <i class="fas fa-download"></i>
                    PDF
                </a>
                <button class="action-btn delete-btn" data-filename="${file.name}">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        `;

        // Add event listeners
        const viewBtn = div.querySelector('.view-btn');
        const costBtn = div.querySelector('.cost-btn');
        const deleteBtn = div.querySelector('.delete-btn');

        viewBtn.addEventListener('click', () => viewFile(file.name));
        costBtn.addEventListener('click', () => showCostDetails(file.name));
        deleteBtn.addEventListener('click', () => deleteFile(file.name));

        // Add download event listeners for analytics
        const downloadBtns = div.querySelectorAll('.download-btn');
        downloadBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const format = btn.textContent.trim();
                showToast(`Downloading ${file.name} as ${format}...`, 'info');
            });
        });

        // Add original PDF button event listener
        const originalBtn = div.querySelector('.original-btn');
        if (originalBtn) {
            originalBtn.addEventListener('click', (e) => {
                showToast(`Opening original PDF: ${file.name}`, 'info');
            });
        }

        // Load cost information
        loadCostInfo(file.name);

        return div;
    }

    // View File
    function viewFile(filename) {
        showToast('Loading document preview...', 'info');
        
        fetch(`/view/${filename}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error('Document not found or not ready');
                }
                return response.json();
            })
            .then(data => {
                // Configure marked.js to prevent false code block detection
                const renderer = new marked.Renderer();
                
                // Override code block renderer to treat code blocks as regular paragraphs
                renderer.code = function(code, language) {
                    return '<p>' + code.replace(/\n/g, '<br>') + '</p>';
                };
                
                // Override inline code renderer to treat inline code as regular text
                renderer.codespan = function(code) {
                    return code;
                };
                
                // Configure marked options
                marked.setOptions({
                    renderer: renderer,
                    breaks: true,
                    gfm: true,
                    sanitize: false
                });
                
                // Preprocess content to remove excessive indentation that triggers code blocks
                let processedContent = data.content
                    .replace(/^(\s{4,})/gm, '') // Remove 4+ spaces at line start
                    .replace(/^\t+/gm, ''); // Remove tabs at line start
                
                modalContent.innerHTML = marked.parse(processedContent);
                modal.style.display = 'block';
                document.body.style.overflow = 'hidden'; // Prevent background scrolling
            })
            .catch(error => {
                console.error('Error viewing file:', error);
                showToast('Error loading document preview. Translation may still be in progress.', 'error');
            });
    }

    // Delete File
    function deleteFile(filename) {
        if (!confirm(`Are you sure you want to delete "${filename}"? This action cannot be undone.`)) {
            return;
        }

        showToast('Deleting document...', 'info');

        fetch(`/delete/${filename}`, { method: 'POST' })
            .then(response => {
                if (response.ok) {
                    showToast('Document deleted successfully', 'success');
                    fetchFiles();
                } else {
                    throw new Error('Delete failed');
                }
            })
            .catch(error => {
                console.error('Error deleting file:', error);
                showToast('Error deleting document', 'error');
            });
    }

    // Update Files Count
    function updateFilesCount(count) {
        filesCount.textContent = count;
    }

    // Toast Notifications
    function showToast(message, type = 'info', duration = 4000) {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        
        const icon = getToastIcon(type);
        toast.innerHTML = `
            <div style="display: flex; align-items: center; gap: 0.5rem;">
                <i class="${icon}"></i>
                <span>${message}</span>
            </div>
        `;

        toastContainer.appendChild(toast);

        // Auto remove toast
        setTimeout(() => {
            toast.style.animation = 'slideOutRight 0.3s ease forwards';
            setTimeout(() => {
                if (toast.parentNode) {
                    toast.parentNode.removeChild(toast);
                }
            }, 300);
        }, duration);

        // Click to dismiss
        toast.addEventListener('click', () => {
            toast.style.animation = 'slideOutRight 0.3s ease forwards';
            setTimeout(() => {
                if (toast.parentNode) {
                    toast.parentNode.removeChild(toast);
                }
            }, 300);
        });
    }

    // Get Toast Icon
    function getToastIcon(type) {
        switch (type) {
            case 'success':
                return 'fas fa-check-circle';
            case 'error':
                return 'fas fa-exclamation-circle';
            case 'info':
            default:
                return 'fas fa-info-circle';
        }
    }

    // Modal close on escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && modal.style.display === 'block') {
            modal.style.display = 'none';
            document.body.style.overflow = 'auto';
        }
    });

    // Close modal handler
    function closeModal() {
        modal.style.display = 'none';
        document.body.style.overflow = 'auto';
    }

    // Update close button event listener
    closeButton.addEventListener('click', closeModal);

    // Add slide out animation for toasts
    const style = document.createElement('style');
    style.textContent = `
        @keyframes slideOutRight {
            from {
                opacity: 1;
                transform: translateX(0);
            }
            to {
                opacity: 0;
                transform: translateX(100px);
            }
        }
    `;
    document.head.appendChild(style);

    // Add keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        // Ctrl/Cmd + U for upload
        if ((e.ctrlKey || e.metaKey) && e.key === 'u') {
            e.preventDefault();
            fileInput.click();
        }
    });

    // Add drag and drop visual feedback
    let dragCounter = 0;

    document.addEventListener('dragenter', (e) => {
        e.preventDefault();
        dragCounter++;
        if (e.dataTransfer.types.includes('Files')) {
            document.body.classList.add('drag-active');
        }
    });

    document.addEventListener('dragleave', (e) => {
        e.preventDefault();
        dragCounter--;
        if (dragCounter === 0) {
            document.body.classList.remove('drag-active');
        }
    });

    document.addEventListener('drop', (e) => {
        e.preventDefault();
        dragCounter = 0;
        document.body.classList.remove('drag-active');
    });

    // Load Cost Information
    function loadCostInfo(filename) {
        fetch(`/cost/${filename}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error('Cost info not available');
                }
                return response.json();
            })
            .then(data => {
                const costElement = document.getElementById(`cost-${filename}`);
                if (costElement) {
                    const costSpan = costElement.querySelector('.cost-loading');
                    if (costSpan) {
                        costSpan.textContent = `$${data.total_cost.toFixed(4)}`;
                        costSpan.className = 'cost-amount';
                    }
                }
            })
            .catch(error => {
                const costElement = document.getElementById(`cost-${filename}`);
                if (costElement) {
                    const costSpan = costElement.querySelector('.cost-loading');
                    if (costSpan) {
                        costSpan.textContent = 'N/A';
                        costSpan.className = 'cost-unavailable';
                    }
                }
            });
    }

    // Show Cost Details
    function showCostDetails(filename) {
        showToast('Loading cost details...', 'info');
        
        fetch(`/cost/${filename}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error('Cost information not available');
                }
                return response.json();
            })
            .then(data => {
                displayCostModal(data);
            })
            .catch(error => {
                console.error('Error loading cost details:', error);
                showToast('Cost information not available for this document', 'error');
            });
    }

    // Display Cost Modal
    function displayCostModal(costData) {
        const modalTitle = document.querySelector('.modal-title');
        modalTitle.textContent = `Cost Analysis - ${costData.filename}`;
        
        modalContent.innerHTML = `
            <div class="cost-summary">
                <div class="cost-header">
                    <h3><i class="fas fa-chart-line"></i> Translation Cost Summary</h3>
                    <div class="total-cost">
                        <span class="cost-label">Total Cost:</span>
                        <span class="cost-value">$${costData.total_cost.toFixed(6)}</span>
                    </div>
                </div>
                
                <div class="cost-breakdown">
                    <div class="cost-section">
                        <h4><i class="fas fa-info-circle"></i> Overview</h4>
                        <div class="cost-grid">
                            <div class="cost-item">
                                <span class="label">Total API Calls:</span>
                                <span class="value">${costData.total_calls}</span>
                            </div>
                            <div class="cost-item">
                                <span class="label">Input Tokens:</span>
                                <span class="value">${costData.total_input_tokens.toLocaleString()}</span>
                            </div>
                            <div class="cost-item">
                                <span class="label">Output Tokens:</span>
                                <span class="value">${costData.total_output_tokens.toLocaleString()}</span>
                            </div>
                            <div class="cost-item">
                                <span class="label">Cost per Page:</span>
                                <span class="value">$${costData.cost_per_page.toFixed(6)}</span>
                            </div>
                        </div>
                    </div>
                    
                    <div class="cost-section">
                        <h4><i class="fas fa-tasks"></i> Operation Breakdown</h4>
                        <div class="operation-breakdown">
                            <div class="operation-item">
                                <div class="operation-header">
                                    <span class="operation-name">
                                        <i class="fas fa-file-text"></i> Transcription
                                    </span>
                                    <span class="operation-cost">$${costData.breakdown.transcription.cost.toFixed(6)}</span>
                                </div>
                                <div class="operation-details">
                                    <span>${costData.breakdown.transcription.calls} calls</span>
                                    <span>Avg: $${costData.breakdown.transcription.avg_cost_per_call.toFixed(6)}/call</span>
                                </div>
                            </div>
                            
                            <div class="operation-item">
                                <div class="operation-header">
                                    <span class="operation-name">
                                        <i class="fas fa-language"></i> Translation
                                    </span>
                                    <span class="operation-cost">$${costData.breakdown.translation.cost.toFixed(6)}</span>
                                </div>
                                <div class="operation-details">
                                    <span>${costData.breakdown.translation.calls} calls</span>
                                    <span>Avg: $${costData.breakdown.translation.avg_cost_per_call.toFixed(6)}/call</span>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="cost-section">
                        <h4><i class="fas fa-dollar-sign"></i> Pricing Information</h4>
                        <div class="pricing-info">
                            <div class="pricing-tier">
                                <strong>Input Tokens:</strong>
                                <div>${costData.pricing_info.input_tier1}</div>
                                <div>${costData.pricing_info.input_tier2}</div>
                            </div>
                            <div class="pricing-tier">
                                <strong>Output Tokens:</strong>
                                <div>${costData.pricing_info.output_tier1}</div>
                                <div>${costData.pricing_info.output_tier2}</div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="cost-footer">
                        <small><i class="fas fa-clock"></i> Generated: ${new Date(costData.timestamp).toLocaleString()}</small>
                    </div>
                </div>
            </div>
        `;
        
        modal.style.display = 'block';
        document.body.style.overflow = 'hidden';
    }

    // Add global drag styles
    const dragStyle = document.createElement('style');
    dragStyle.textContent = `
        body.drag-active::after {
            content: 'Drop PDF file anywhere to upload';
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(99, 102, 241, 0.9);
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.5rem;
            font-weight: 600;
            z-index: 10000;
            pointer-events: none;
        }
    `;
    document.head.appendChild(dragStyle);
});
