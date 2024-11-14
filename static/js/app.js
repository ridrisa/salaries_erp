$(document).ready(function() {
    // Global variables
    let currentCategory = null;
    let customParams = {};
    let currentData = [];
    let salaryChart = null;
    let bonusChart = null;

    // Initialize Select2 for better dropdowns (if used)
    $('.select2').select2({
        theme: 'bootstrap-5',
        width: '100%'
    });

    // Category button click
    $('.category-btn').click(function() {
        currentCategory = $(this).data('category');
        $('.category-btn').removeClass('active');
        $(this).addClass('active');
    });

    // Calculate Salaries button
    $('#calculateSalariesBtn').click(function() {
        const month = $('#month').val();
        const year = $('#year').val();

        if (!currentCategory) {
            showToast("Please select a category to calculate salaries.", "warning");
            return;
        }
        if (!month || !year) {
            showToast("Please select both month and year.", "warning");
            return;
        }

        fetchSalaries(currentCategory, month, year);
    });

    // Fetch salaries and update current data
    function fetchSalaries(category, month, year) {
        $('#loadingSpinner').removeClass('d-none');
        $('#results').addClass('d-none');
        $('#dashboard').addClass('d-none');
        $('#calculateSalariesBtn').prop('disabled', true).append('<span class="spinner-border spinner-border-sm ms-2"></span>');

        $.ajax({
            url: '/calculate_salary',
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ category, month, year, customParams }),
            success: function(response) {
                if (response.data && response.data.length > 0) {
                    currentData = response.data;
                    renderResults(response.data);
                    updateDashboard(response.data); // Update insights and charts
                    showToast("Salaries calculated successfully.", "success");
                } else {
                    showToast("No salary data found for the selected criteria.", "warning");
                }
            },
            error: function(err) {
                console.error(err);
                const errorMsg = err.responseJSON && err.responseJSON.error ? err.responseJSON.error : "Error fetching salary data.";
                showToast(errorMsg, "danger");
            },
            complete: function() {
                $('#loadingSpinner').addClass('d-none');
                $('#results').removeClass('d-none');
                $('#dashboard').removeClass('d-none');
                $('#calculateSalariesBtn').prop('disabled', false).find('.spinner-border').remove();
            }
        });
    }

    // Render results in the table
    function renderResults(data) {
        const tableHead = $('#salaryTable thead');
        const tableBody = $('#salaryTable tbody');
        tableHead.empty();
        tableBody.empty();

        const headers = getHeaders();

        // Render table headers
        const headerRow = $('<tr></tr>');
        headers.forEach(headerObj => {
            headerRow.append(`<th>${headerObj.header}</th>`);
        });
        tableHead.append(headerRow);

        // Render table body
        data.forEach(record => {
            const row = $('<tr></tr>');
            headers.forEach(headerObj => {
                if (headerObj.key === 'Actions') {
                    const actionTd = $('<td class="table-actions"></td>');
                    const detailsBtn = $('<button class="btn btn-primary btn-sm view-details me-2"><i class="fas fa-info-circle"></i> Details</button>');
                    const payslipBtn = $('<button class="btn btn-secondary btn-sm generate-payslip-btn"><i class="fas fa-file-pdf"></i> Payslip</button>');

                    detailsBtn.data('record', record);
                    payslipBtn.data('record', record);

                    actionTd.append(detailsBtn).append(payslipBtn);
                    row.append(actionTd);
                } else {
                    let cellData = getNestedValue(record, headerObj.key);
                    cellData = headerObj.format ? headerObj.format(cellData) : cellData;
                    row.append(`<td>${cellData !== undefined ? cellData : ''}</td>`);
                }
            });
            tableBody.append(row);
        });

        attachEventListeners();
    }

    // Attach event listeners to dynamically generated buttons
    function attachEventListeners() {
        $('.view-details').off('click').on('click', function() {
            const record = $(this).data('record');
            populateModal(record);
            $('#detailModal').modal('show');
        });

        $('.generate-payslip-btn').off('click').on('click', function() {
            const record = $(this).data('record');
            generatePayslip(record);
        });
    }

    // Generate payslip as PDF
    function generatePayslip(record) {
        if (!record || !record.period) {
            showToast("Period information missing, cannot generate payslip.", "danger");
            return;
        }

        const payslipContent = createPayslipContent(record);
        const element = document.createElement('div');
        element.innerHTML = payslipContent;
        document.body.appendChild(element);

        const opt = {
            margin:       0.5,
            filename:     `payslip_${record.BARQ_ID}_${record.period.start_date}.pdf`,
            image:        { type: 'jpeg', quality: 0.98 },
            html2canvas:  { scale: 2 },
            jsPDF:        { unit: 'in', format: 'a4', orientation: 'portrait' }
        };

        html2pdf().set(opt).from(element).save().then(() => {
            document.body.removeChild(element);
            showToast("Payslip generated successfully.", "success");
        }).catch(error => {
            console.error('Payslip generation error:', error);
            showToast("Error generating payslip", "danger");
        });
    }

    // Create payslip content for PDF
    function createPayslipContent(record) {
        const logoUrl = '/static/images/logo3.png'; // Adjust the path as necessary

        return `
        <div style="font-family: Arial, sans-serif; color: #333;">
            <div style="text-align: center; margin-bottom: 20px;">
                <img src="${logoUrl}" alt="Barq Logo" style="width: 100px; height: 100px;">
                <h2>Barq Delivery Services</h2>
                <p>Riyadh, Saudi Arabia</p>
            </div>
            <h3 style="text-align: center; margin-bottom: 20px;">Salary Slip</h3>
            <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
                <tr>
                    <th style="border: 1px solid #ddd; padding: 8px;">BARQ ID</th>
                    <td style="border: 1px solid #ddd; padding: 8px;">${record.BARQ_ID}</td>
                </tr>
                <tr>
                    <th style="border: 1px solid #ddd; padding: 8px;">Name</th>
                    <td style="border: 1px solid #ddd; padding: 8px;">${record.Name}</td>
                </tr>
                <tr>
                    <th style="border: 1px solid #ddd; padding: 8px;">IBAN</th>
                    <td style="border: 1px solid #ddd; padding: 8px;">${record.iban}</td>
                </tr>
                <tr>
                    <th style="border: 1px solid #ddd; padding: 8px;">ID Number</th>
                    <td style="border: 1px solid #ddd; padding: 8px;">${record.id_number}</td>
                </tr>
                <tr>
                    <th style="border: 1px solid #ddd; padding: 8px;">Joining Date</th>
                    <td style="border: 1px solid #ddd; padding: 8px;">${formatDate(record.joining_Date)}</td>
                </tr>
                <tr>
                    <th style="border: 1px solid #ddd; padding: 8px;">Status</th>
                    <td style="border: 1px solid #ddd; padding: 8px;">${record.Status}</td>
                </tr>
                <tr>
                    <th style="border: 1px solid #ddd; padding: 8px;">Sponsorship Status</th>
                    <td style="border: 1px solid #ddd; padding: 8px;">${record.Sponsorshipstatus}</td>
                </tr>
            </table>

            <h4>Performance Metrics</h4>
            <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
                <tr>
                    <th style="border: 1px solid #ddd; padding: 8px;">Total Orders</th>
                    <td style="border: 1px solid #ddd; padding: 8px;">${record.Total_Orders}</td>
                </tr>
                <tr>
                    <th style="border: 1px solid #ddd; padding: 8px;">Target</th>
                    <td style="border: 1px solid #ddd; padding: 8px;">${record.target}</td>
                </tr>
                <tr>
                    <th style="border: 1px solid #ddd; padding: 8px;">Total Revenue</th>
                    <td style="border: 1px solid #ddd; padding: 8px;">${formatCurrency(record.Total_Revenue)} SAR</td>
                </tr>
                <tr>
                    <th style="border: 1px solid #ddd; padding: 8px;">Gas Usage</th>
                    <td style="border: 1px solid #ddd; padding: 8px;">${formatCurrency(record.Gas_Usage)} SAR</td>
                </tr>
            </table>

            <h4>Salary Breakdown</h4>
            <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
                <tr>
                    <th style="border: 1px solid #ddd; padding: 8px;">Basic Salary</th>
                    <td style="border: 1px solid #ddd; padding: 8px;">${formatCurrency(record.Basic_Salary)} SAR</td>
                </tr>
                <tr>
                    <th style="border: 1px solid #ddd; padding: 8px;">Bonus Amount</th>
                    <td style="border: 1px solid #ddd; padding: 8px;">${formatCurrency(record.Bonus_Amount)} SAR</td>
                </tr>
                <tr>
                    <th style="border: 1px solid #ddd; padding: 8px;">Gas Deserved</th>
                    <td style="border: 1px solid #ddd; padding: 8px;">${formatCurrency(record.Gas_Deserved)} SAR</td>
                </tr>
                <tr>
                    <th style="border: 1px solid #ddd; padding: 8px;">Gas Difference</th>
                    <td style="border: 1px solid #ddd; padding: 8px;">${formatCurrency(record.Gas_Difference)} SAR</td>
                </tr>
                <tr style="background-color: #eaf7ea; font-weight: bold;">
                    <th style="border: 1px solid #ddd; padding: 8px;">Total Salary</th>
                    <td style="border: 1px solid #ddd; padding: 8px;">${formatCurrency(record.Total_Salary)} SAR</td>
                </tr>
            </table>

            <h4>Period</h4>
            <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
                <tr>
                    <th style="border: 1px solid #ddd; padding: 8px;">Start Date</th>
                    <td style="border: 1px solid #ddd; padding: 8px;">${formatDate(record.period.start_date)}</td>
                </tr>
                <tr>
                    <th style="border: 1px solid #ddd; padding: 8px;">End Date</th>
                    <td style="border: 1px solid #ddd; padding: 8px;">${formatDate(record.period.end_date)}</td>
                </tr>
            </table>

            <div style="text-align: center; margin-top: 30px;">
                <p>This is a computer-generated document. No signature is required.</p>
                <p>Generated by Barq Salary Calculator System</p>
            </div>
        </div>`;
    }

    // Render results in the table
    function renderResults(data) {
        const tableHead = $('#salaryTable thead');
        const tableBody = $('#salaryTable tbody');
        tableHead.empty();
        tableBody.empty();

        const headers = getHeaders();

        // Render table headers
        const headerRow = $('<tr></tr>');
        headers.forEach(headerObj => {
            headerRow.append(`<th>${headerObj.header}</th>`);
        });
        tableHead.append(headerRow);

        // Render table body
        data.forEach(record => {
            const row = $('<tr></tr>');
            headers.forEach(headerObj => {
                if (headerObj.key === 'Actions') {
                    const actionTd = $('<td class="table-actions"></td>');
                    const detailsBtn = $('<button class="btn btn-primary btn-sm view-details me-2"><i class="fas fa-info-circle"></i> Details</button>');
                    const payslipBtn = $('<button class="btn btn-secondary btn-sm generate-payslip-btn"><i class="fas fa-file-pdf"></i> Payslip</button>');

                    detailsBtn.data('record', record);
                    payslipBtn.data('record', record);

                    actionTd.append(detailsBtn).append(payslipBtn);
                    row.append(actionTd);
                } else {
                    let cellData = getNestedValue(record, headerObj.key);
                    cellData = headerObj.format ? headerObj.format(cellData) : cellData;
                    row.append(`<td>${cellData !== undefined ? cellData : ''}</td>`);
                }
            });
            tableBody.append(row);
        });

        attachEventListeners();
    }

    // Attach event listeners to dynamically generated buttons
    function attachEventListeners() {
        $('.view-details').off('click').on('click', function() {
            const record = $(this).data('record');
            populateModal(record);
            $('#detailModal').modal('show');
        });

        $('.generate-payslip-btn').off('click').on('click', function() {
            const record = $(this).data('record');
            generatePayslip(record);
        });
    }

    // Generate payslip as PDF
    function generatePayslip(record) {
        if (!record || !record.period) {
            showToast("Period information missing, cannot generate payslip.", "danger");
            return;
        }

        const payslipContent = createPayslipContent(record);
        const element = document.createElement('div');
        element.innerHTML = payslipContent;
        document.body.appendChild(element);

        const opt = {
            margin:       0.5,
            filename:     `payslip_${record.BARQ_ID}_${record.period.start_date}.pdf`,
            image:        { type: 'jpeg', quality: 0.98 },
            html2canvas:  { scale: 2 },
            jsPDF:        { unit: 'in', format: 'a4', orientation: 'portrait' }
        };

        html2pdf().set(opt).from(element).save().then(() => {
            document.body.removeChild(element);
            showToast("Payslip generated successfully.", "success");
        }).catch(error => {
            console.error('Payslip generation error:', error);
            showToast("Error generating payslip", "danger");
        });
    }

    // CSV download handler with spinner
    $('#downloadCsv').click(function() {
        const btn = $(this);
        if (currentData.length === 0) {
            showToast("No data available to download", "warning");
            return;
        }

        btn.prop('disabled', true).append('<span class="spinner-border spinner-border-sm ms-2"></span>');
        setTimeout(() => {
            try {
                const csvContent = createCSVContent(currentData);
                const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
                const link = document.createElement('a');
                link.href = URL.createObjectURL(blob);
                link.download = `salary_data_${new Date().toISOString().slice(0,10)}.csv`;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);

                showToast("CSV downloaded successfully", "success");
            } catch (error) {
                console.error('CSV download error:', error);
                showToast("Error downloading CSV", "danger");
            } finally {
                btn.prop('disabled', false).find('.spinner-border').remove();
            }
        }, 100);
    });

    // Search functionality with debouncing
    $('#searchInput').on('input', debounce(function() {
        const searchTerm = $(this).val().toLowerCase();
        $('#salaryTable tbody tr').each(function() {
            const rowText = $(this).text().toLowerCase();
            $(this).toggle(rowText.includes(searchTerm));
        });
    }, 300));

    // Update Dashboard Section
    function updateDashboard(data) {
        // Calculate total employees
        const totalEmployees = data.length;
        $('#totalEmployees').text(totalEmployees);
    
        // Initialize totals
        let totalSalary = 0;
        let totalBonuses = 0;
        let totalOrders = 0;
    
        data.forEach(record => {
            // Parse numerical values safely
            const salary = parseFloat(record.Total_Salary) || 0;
            const bonus = parseFloat(record.Bonus_Amount) || 0;
            const orders = parseInt(record.Total_Orders) || 0;
    
            totalSalary += salary;
            totalBonuses += bonus;
            totalOrders += orders;
        });
    
        $('#totalSalary').text(formatCurrency(totalSalary));
        $('#totalBonuses').text(formatCurrency(totalBonuses));
        $('#totalOrders').text(totalOrders);
    
        // Update Charts
        updateCharts(data);
    }

    // Update Charts Function
    function updateCharts(data) {
        // Prepare data
        const salaryData = data.map(record => parseFloat(record.Total_Salary) || 0);
        const bonusData = data.map(record => parseFloat(record.Bonus_Amount) || 0);
        const names = data.map(record => record.Name || 'Unknown');

        // Destroy previous charts if they exist
        if (salaryChart) salaryChart.destroy();
        if (bonusChart) bonusChart.destroy();

        // Create salary distribution chart
        const ctxSalary = document.getElementById('salaryDistributionChart').getContext('2d');
        salaryChart = new Chart(ctxSalary, {
            type: 'bar',
            data: {
                labels: names,
                datasets: [{
                    label: 'Total Salary',
                    data: salaryData,
                    backgroundColor: 'rgba(76, 175, 80, 0.6)',
                    borderColor: 'rgba(76, 175, 80, 1)',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            color: '#e0e0e0'
                        }
                    },
                    x: {
                        ticks: {
                            color: '#e0e0e0',
                            maxRotation: 90,
                            minRotation: 45
                        }
                    }
                },
                plugins: {
                    legend: {
                        labels: {
                            color: '#e0e0e0'
                        }
                    }
                }
            }
        });

        // Create bonus distribution chart
        const ctxBonus = document.getElementById('bonusDistributionChart').getContext('2d');
        bonusChart = new Chart(ctxBonus, {
            type: 'bar',
            data: {
                labels: names,
                datasets: [{
                    label: 'Bonus Amount',
                    data: bonusData,
                    backgroundColor: 'rgba(0, 188, 212, 0.6)',
                    borderColor: 'rgba(0, 188, 212, 1)',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            color: '#e0e0e0'
                        }
                    },
                    x: {
                        ticks: {
                            color: '#e0e0e0',
                            maxRotation: 90,
                            minRotation: 45
                        }
                    }
                },
                plugins: {
                    legend: {
                        labels: {
                            color: '#e0e0e0'
                        }
                    }
                }
            }
        });
    }

    // Collect parameters from modal form
    function collectParams() {
        const params = {};
        $('#parameterFields input').each(function() {
            const paramId = $(this).attr('id');
            const paramValue = parseFloat($(this).val());
            if (!isNaN(paramValue)) {
                params[paramId] = paramValue;
            }
        });
        return params;
    }

    // Display parameter fields based on category
    function displayParameterFields(category) {
        const fields = getParameterFields(category);
        const parameterFieldsContainer = $('#parameterFields');
        parameterFieldsContainer.empty();

        fields.forEach(field => {
            const fieldHtml = `
                <div class="mb-3">
                    <label for="${field.id}" class="form-label">${field.label}</label>
                    <input type="number" step="any" class="form-control bg-dark text-light border-secondary" id="${field.id}" placeholder="${field.placeholder}" required>
                </div>
            `;
            parameterFieldsContainer.append(fieldHtml);
        });
    }

    // Get parameter fields based on category
    function getParameterFields(category) {
        const parameterFields = {
            "Motorcycle": [
                { label: "Basic Salary Rate", id: "motorcycle_basic_salary_rate", placeholder: "e.g., 53.33333" },
                { label: "Bonus Rate", id: "motorcycle_bonus_rate", placeholder: "e.g., 6" },
                { label: "Penalty Rate", id: "motorcycle_penalty_rate", placeholder: "e.g., 10" },
                { label: "Gas Rate", id: "motorcycle_gas_rate", placeholder: "e.g., 0.65" },
                { label: "Gas Cap", id: "motorcycle_gas_cap", placeholder: "e.g., 261" }
            ],
            "Food Trial": [
                { label: "Basic Salary Rate", id: "food_trial_basic_salary_rate", placeholder: "e.g., 66.66667" },
                { label: "Bonus Rate", id: "food_trial_bonus_rate", placeholder: "e.g., 7" },
                { label: "Penalty Rate", id: "food_trial_penalty_rate", placeholder: "e.g., 10" },
                { label: "Gas Rate", id: "food_trial_gas_rate", placeholder: "e.g., 2.11" },
                { label: "Gas Cap", id: "food_trial_gas_cap", placeholder: "e.g., 826" }
            ],
            "Food In-House New": [
                { label: "Basic Salary Rate", id: "food_inhouse_new_basic_salary_rate", placeholder: "e.g., 66.66667" },
                { label: "Bonus Rate", id: "food_inhouse_new_bonus_rate", placeholder: "e.g., 7" },
                { label: "Penalty Rate", id: "food_inhouse_new_penalty_rate", placeholder: "e.g., 10" },
                { label: "Gas Rate", id: "food_inhouse_new_gas_rate", placeholder: "e.g., 1.739" },
                { label: "Gas Cap", id: "food_inhouse_new_gas_cap", placeholder: "e.g., 826" }
            ],
            "Food In-House Old": [
                { label: "Basic Salary Rate", id: "food_inhouse_old_basic_salary_rate", placeholder: "e.g., 66.66667" },
                { label: "Penalty Rate", id: "food_inhouse_old_penalty_rate", placeholder: "e.g., 10" },
                { label: "Gas Rate", id: "food_inhouse_old_gas_rate", placeholder: "e.g., 2.065" },
                { label: "Gas Cap", id: "food_inhouse_old_gas_cap", placeholder: "e.g., 826" }
            ],
            "Ecommerce WH": [
                { label: "Basic Salary Rate", id: "ecommerce_wh_basic_salary_rate", placeholder: "e.g., 66.66667" },
                { label: "Bonus Rate", id: "ecommerce_wh_bonus_rate", placeholder: "e.g., 8" },
                { label: "Penalty Rate", id: "ecommerce_wh_penalty_rate", placeholder: "e.g., 10" },
                { label: "Gas Rate", id: "ecommerce_wh_gas_rate", placeholder: "e.g., 15.03" },
                { label: "Gas Cap", id: "ecommerce_wh_gas_cap", placeholder: "e.g., 452" }
            ],
            "Ecommerce": [
                { label: "Basic Salary Rate", id: "ecommerce_basic_salary_rate", placeholder: "e.g., 66.66667" },
                { label: "Revenue Coefficient", id: "ecommerce_revenue_coefficient", placeholder: "e.g., 0.3017" },
                { label: "Gas Cap", id: "ecommerce_gas_cap", placeholder: "e.g., 452" }
            ],
            "Ajeer": [
                { label: "Basic Salary Rate", id: "ajeer_basic_salary_rate", placeholder: "e.g., 53.33333" },
                { label: "Penalty Rate", id: "ajeer_penalty_rate", placeholder: "e.g., 10" },
                { label: "Gas Rate", id: "ajeer_gas_rate", placeholder: "e.g., 2.065" },
                { label: "Gas Cap", id: "ajeer_gas_cap", placeholder: "e.g., 826" }
            ]
        };
        return parameterFields[category] || [];
    }

    // Get table headers
    function getHeaders() {
        return [
            { header: 'BARQ ID', key: 'BARQ_ID' },
            { header: 'Name', key: 'Name' },
            { header: 'IBAN', key: 'iban' },
            { header: 'ID Number', key: 'id_number' },
            { header: 'Joining Date', key: 'joining_Date', format: formatDate },
            { header: 'Status', key: 'Status' },
            { header: 'Sponsorship Status', key: 'Sponsorshipstatus' },
            { header: 'Project', key: 'PROJECT' },
            { header: 'Supervisor', key: 'Supervisor' },
            { header: 'Total Orders', key: 'Total_Orders' },
            { header: 'Total Revenue', key: 'Total_Revenue', format: formatCurrency },
            { header: 'Gas Usage', key: 'Gas_Usage', format: formatCurrency },
            { header: 'Basic Salary', key: 'Basic_Salary', format: formatCurrency },
            { header: 'Bonus Amount', key: 'Bonus_Amount', format: formatCurrency },
            { header: 'Gas Deserved', key: 'Gas_Deserved', format: formatCurrency },
            { header: 'Gas Difference', key: 'Gas_Difference', format: formatCurrency },
            { header: 'Total Salary', key: 'Total_Salary', format: formatCurrency },
            { header: 'Start Period', key: 'period.start_date', format: formatDate },
            { header: 'End Period', key: 'period.end_date', format: formatDate },
            { header: 'Target', key: 'target' },
            { header: 'Days Since Joining', key: 'days_since_joining' },
            { header: 'Actions', key: 'Actions' }
        ];
    }

    // Get nested value from an object
    function getNestedValue(obj, key) {
        return key.split('.').reduce((o, x) => (o === undefined || o === null) ? o : o[x], obj);
    }

    // Create payslip content for PDF
    function createPayslipContent(record) {
        const logoUrl = '/static/images/logo3.png'; // Adjust the path as necessary

        return `
        <div style="font-family: Arial, sans-serif; color: #333;">
            <div style="text-align: center; margin-bottom: 20px;">
                <img src="${logoUrl}" alt="Barq Logo" style="width: 100px; height: 100px;">
                <h2>Barq Delivery Services</h2>
                <p>Riyadh, Saudi Arabia</p>
            </div>
            <h3 style="text-align: center; margin-bottom: 20px;">Salary Slip</h3>
            <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
                <tr>
                    <th style="border: 1px solid #ddd; padding: 8px;">BARQ ID</th>
                    <td style="border: 1px solid #ddd; padding: 8px;">${record.BARQ_ID}</td>
                </tr>
                <tr>
                    <th style="border: 1px solid #ddd; padding: 8px;">Name</th>
                    <td style="border: 1px solid #ddd; padding: 8px;">${record.Name}</td>
                </tr>
                <tr>
                    <th style="border: 1px solid #ddd; padding: 8px;">IBAN</th>
                    <td style="border: 1px solid #ddd; padding: 8px;">${record.iban}</td>
                </tr>
                <tr>
                    <th style="border: 1px solid #ddd; padding: 8px;">ID Number</th>
                    <td style="border: 1px solid #ddd; padding: 8px;">${record.id_number}</td>
                </tr>
                <tr>
                    <th style="border: 1px solid #ddd; padding: 8px;">Joining Date</th>
                    <td style="border: 1px solid #ddd; padding: 8px;">${formatDate(record.joining_Date)}</td>
                </tr>
                <tr>
                    <th style="border: 1px solid #ddd; padding: 8px;">Status</th>
                    <td style="border: 1px solid #ddd; padding: 8px;">${record.Status}</td>
                </tr>
                <tr>
                    <th style="border: 1px solid #ddd; padding: 8px;">Sponsorship Status</th>
                    <td style="border: 1px solid #ddd; padding: 8px;">${record.Sponsorshipstatus}</td>
                </tr>
            </table>

            <h4>Performance Metrics</h4>
            <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
                <tr>
                    <th style="border: 1px solid #ddd; padding: 8px;">Total Orders</th>
                    <td style="border: 1px solid #ddd; padding: 8px;">${record.Total_Orders}</td>
                </tr>
                <tr>
                    <th style="border: 1px solid #ddd; padding: 8px;">Target</th>
                    <td style="border: 1px solid #ddd; padding: 8px;">${record.target}</td>
                </tr>
                <tr>
                    <th style="border: 1px solid #ddd; padding: 8px;">Total Revenue</th>
                    <td style="border: 1px solid #ddd; padding: 8px;">${formatCurrency(record.Total_Revenue)} SAR</td>
                </tr>
                <tr>
                    <th style="border: 1px solid #ddd; padding: 8px;">Gas Usage</th>
                    <td style="border: 1px solid #ddd; padding: 8px;">${formatCurrency(record.Gas_Usage)} SAR</td>
                </tr>
            </table>

            <h4>Salary Breakdown</h4>
            <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
                <tr>
                    <th style="border: 1px solid #ddd; padding: 8px;">Basic Salary</th>
                    <td style="border: 1px solid #ddd; padding: 8px;">${formatCurrency(record.Basic_Salary)} SAR</td>
                </tr>
                <tr>
                    <th style="border: 1px solid #ddd; padding: 8px;">Bonus Amount</th>
                    <td style="border: 1px solid #ddd; padding: 8px;">${formatCurrency(record.Bonus_Amount)} SAR</td>
                </tr>
                <tr>
                    <th style="border: 1px solid #ddd; padding: 8px;">Gas Deserved</th>
                    <td style="border: 1px solid #ddd; padding: 8px;">${formatCurrency(record.Gas_Deserved)} SAR</td>
                </tr>
                <tr>
                    <th style="border: 1px solid #ddd; padding: 8px;">Gas Difference</th>
                    <td style="border: 1px solid #ddd; padding: 8px;">${formatCurrency(record.Gas_Difference)} SAR</td>
                </tr>
                <tr style="background-color: #eaf7ea; font-weight: bold;">
                    <th style="border: 1px solid #ddd; padding: 8px;">Total Salary</th>
                    <td style="border: 1px solid #ddd; padding: 8px;">${formatCurrency(record.Total_Salary)} SAR</td>
                </tr>
            </table>

            <h4>Period</h4>
            <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
                <tr>
                    <th style="border: 1px solid #ddd; padding: 8px;">Start Date</th>
                    <td style="border: 1px solid #ddd; padding: 8px;">${formatDate(record.period.start_date)}</td>
                </tr>
                <tr>
                    <th style="border: 1px solid #ddd; padding: 8px;">End Date</th>
                    <td style="border: 1px solid #ddd; padding: 8px;">${formatDate(record.period.end_date)}</td>
                </tr>
            </table>

            <div style="text-align: center; margin-top: 30px;">
                <p>This is a computer-generated document. No signature is required.</p>
                <p>Generated by Barq Salary Calculator System</p>
            </div>
        </div>`;
    }

    // Create CSV content
    function createCSVContent(data) {
        const headers = [
            'BARQ ID', 'Name', 'IBAN', 'ID Number', 'Joining Date',
            'Status', 'Sponsorship Status', 'Project', 'Supervisor',
            'Total Orders', 'Total Revenue', 'Gas Usage', 'Basic Salary',
            'Bonus Amount', 'Gas Deserved', 'Gas Difference', 'Total Salary',
            'Start Period', 'End Period', 'Target', 'Days Since Joining'
        ];

        let csvContent = headers.join(',') + '\n';

        data.forEach(record => {
            const row = [
                record.BARQ_ID,
                `"${record.Name}"`,
                record.iban,
                record.id_number,
                formatDate(record.joining_Date),
                record.Status,
                record.Sponsorshipstatus,
                record.PROJECT,
                `"${record.Supervisor}"`,
                record.Total_Orders,
                record.Total_Revenue,
                record.Gas_Usage,
                record.Basic_Salary,
                record.Bonus_Amount,
                record.Gas_Deserved,
                record.Gas_Difference,
                record.Total_Salary,
                formatDate(record.period.start_date),
                formatDate(record.period.end_date),
                record.target,
                record.days_since_joining
            ].join(',');
            csvContent += row + '\n';
        });

        return csvContent;
    }

    // Format currency values
    function formatCurrency(value) {
        return new Intl.NumberFormat('en-SA', {
            style: 'currency',
            currency: 'SAR'
        }).format(value);
    }

    // Format date values
    function formatDate(dateString) {
        return new Date(dateString).toLocaleDateString('en-SA');
    }

    // Debounce function
    function debounce(func, wait) {
        let timeout;
        return function(...args) {
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(this, args), wait);
        };
    }

    // Show toast notifications
    function showToast(message, type) {
        const toastId = `toast_${Date.now()}`;
        const iconClass = type === 'success' ? 'check-circle' :
                          type === 'warning' ? 'exclamation-triangle' :
                          'exclamation-circle';
        const toastHtml = `
            <div id="${toastId}" class="toast align-items-center text-white bg-${type} border-0 mb-2" role="alert" aria-live="assertive" aria-atomic="true">
                <div class="d-flex">
                    <div class="toast-body">
                        <i class="fas fa-${iconClass} me-2"></i>${message}
                    </div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
                </div>
            </div>
        `;
        $('.toast-container').append(toastHtml);
        new bootstrap.Toast(document.getElementById(toastId), { delay: 3000 }).show();
    }

    // Populate modal with all salary details
    function populateModal(record) {
        const modalBody = $('#detailModalContent');
        modalBody.html(`
            <h4>Employee Information</h4>
            <table class="table table-bordered">
                <tr><th>BARQ ID</th><td>${record.BARQ_ID}</td></tr>
                <tr><th>Name</th><td>${record.Name}</td></tr>
                <tr><th>IBAN</th><td>${record.iban}</td></tr>
                <tr><th>ID Number</th><td>${record.id_number}</td></tr>
                <tr><th>Joining Date</th><td>${formatDate(record.joining_Date)}</td></tr>
                <tr><th>Status</th><td>${record.Status}</td></tr>
                <tr><th>Sponsorship Status</th><td>${record.Sponsorshipstatus}</td></tr>
                <tr><th>Project</th><td>${record.PROJECT}</td></tr>
                <tr><th>Supervisor</th><td>${record.Supervisor}</td></tr>
                <tr><th>Total Orders</th><td>${record.Total_Orders}</td></tr>
                <tr><th>Total Revenue</th><td>${formatCurrency(record.Total_Revenue)} SAR</td></tr>
                <tr><th>Gas Usage</th><td>${formatCurrency(record.Gas_Usage)} SAR</td></tr>
                <tr><th>Basic Salary</th><td>${formatCurrency(record.Basic_Salary)} SAR</td></tr>
                <tr><th>Bonus Amount</th><td>${formatCurrency(record.Bonus_Amount)} SAR</td></tr>
                <tr><th>Gas Deserved</th><td>${formatCurrency(record.Gas_Deserved)} SAR</td></tr>
                <tr><th>Gas Difference</th><td>${formatCurrency(record.Gas_Difference)} SAR</td></tr>
                <tr><th>Total Salary</th><td>${formatCurrency(record.Total_Salary)} SAR</td></tr>
                <tr><th>Start Period</th><td>${formatDate(record.period.start_date)}</td></tr>
                <tr><th>End Period</th><td>${formatDate(record.period.end_date)}</td></tr>
                <tr><th>Target</th><td>${record.target}</td></tr>
                <tr><th>Days Since Joining</th><td>${record.days_since_joining}</td></tr>
            </table>
        `);
    }

});
