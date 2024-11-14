// Global Variables for Pagination and Courier Data
let courierCurrentPage = 1;
let couriersPerPage = 10;
let courierTotalCount = 0;
let courierList = [];

document.addEventListener('DOMContentLoaded', function() {
    // Initialize select2 for searchable dropdowns
    $('.select2').select2({
        theme: 'default',
        width: '100%'
    });

    // Load scorecards data on page load
    loadScorecardsData();
    fetchCouriers();

    // Handle filters and courier selection
    const filterButton = document.getElementById('filter-button');
    if (filterButton) {
        filterButton.addEventListener('click', function() {
            fetchCourierData();
        });
    } else {
        console.error('Filter button not found.');
    }

    const closeButton = document.querySelector('.close-btn');
    if (closeButton) {
        closeButton.addEventListener('click', function() {
            closeModal();
        });
    }

    function loadScorecardsData() {
        const scorecards = [
            { id: 'total-active-couriers', endpoint: '/get_total_active_couriers' },
            { id: 'active-ecommerce-couriers', endpoint: '/get_active_ecommerce_couriers' },
            { id: 'active-food-couriers', endpoint: '/get_active_food_couriers' },
            { id: 'active-motorcycle-couriers', endpoint: '/get_active_motorcycle_couriers' },
            { id: 'inhouse-couriers', endpoint: '/get_inhouse_couriers' },
            { id: 'ajeer-couriers', endpoint: '/get_ajeer_couriers' }
        ];

        scorecards.forEach(scorecard => {
            const loaderElement = document.getElementById(`loader-${scorecard.id}`);
            const scorecardElement = document.getElementById(scorecard.id);
            if (loaderElement) {
                loaderElement.style.display = 'block';
            }

            fetch(scorecard.endpoint)
                .then(response => response.json())
                .then(data => {
                    if (scorecardElement) {
                        scorecardElement.textContent = data.count;
                    }
                })
                .finally(() => {
                    if (loaderElement) {
                        loaderElement.style.display = 'none';
                    }
                })
                .catch(error => console.error(`Error fetching data for ${scorecard.id}:`, error));
        });
    }

    function fetchCouriers() {
        const courierInfo = document.getElementById('courier-info');
        const loader = document.getElementById('loader');

        if (courierInfo) {
            courierInfo.innerHTML = '';
        }

        if (loader) {
            loader.style.display = 'block';
        }

        fetch('/get_all_couriers')
            .then(response => response.json())
            .then(data => {
                if (loader) {
                    loader.style.display = 'none';
                }

                courierList = data.couriers;
                courierTotalCount = courierList.length;
                renderTable();
            })
            .catch(error => {
                if (loader) {
                    loader.style.display = 'none';
                }
                if (courierInfo) {
                    courierInfo.innerHTML = '<p>Failed to retrieve data. Please try again later.</p>';
                }
                console.error('Error:', error);
            });
    }

    function fetchCourierData() {
        const courierInfo = document.getElementById('courier-info');
        const loader = document.getElementById('loader');
        const courierDetails = document.getElementById('courier-details');

        if (courierInfo) {
            courierInfo.innerHTML = '';
        }

        if (loader) {
            loader.style.display = 'block';
        }

        const courierName = document.getElementById('courier-select').value;
        const filterDate = document.getElementById('filter-date').value;
        const filterBARQ_ID = document.getElementById('filter-BARQ_ID').value;
        const filterStatus = document.getElementById('filter-status').value;
        const filterIdNumber = document.getElementById('filter-id-number').value;
        const filterSponsorship = document.getElementById('filter-sponsorship').value;

        fetch('/get_courier_data', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                courier_name: courierName,
                filter_date: filterDate,
                filter_BARQ_ID: filterBARQ_ID,
                filter_status: filterStatus,
                filter_id_number: filterIdNumber,
                filter_sponsorship: filterSponsorship
            })
        })
        .then(response => response.json())
        .then(data => {
            if (loader) {
                loader.style.display = 'none';
            }

            courierList = data.courier_data;
            courierTotalCount = courierList.length;
            renderTable();

            if (courierList.length === 1) {
                fetchCourierDetails(courierList[0].BARQ_ID);
            } else if (courierList.length === 0) {
                courierInfo.innerHTML = '<p>No data found for the selected courier or filters.</p>';
            }
        })
        .catch(error => {
            if (loader) {
                loader.style.display = 'none';
            }
            if (courierInfo) {
                courierInfo.innerHTML = '<p>Failed to retrieve data. Please try again later.</p>';
            }
            console.error('Error:', error);
        });
    }

    function fetchCourierDetails(barqId) {
        fetch(`/get_courier_details?barq_id=${barqId}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (data.courier) {
                    openModal(data.courier);
                } else {
                    console.error('Courier details not found');
                }
            })
            .catch(error => console.error('Error fetching courier details:', error));
    }

    function changeRowsPerPage() {
        couriersPerPage = parseInt(document.getElementById('rowsPerPage').value);
        courierCurrentPage = 1; // Reset to first page
        fetchCouriers();
    }

    function renderTable() {
        const tableBody = document.getElementById('courierTable').getElementsByTagName('tbody')[0];
        if (!tableBody) {
            console.error('Table body element not found.');
            return;
        }
        tableBody.innerHTML = ''; // Clear existing table content

        courierList.slice((courierCurrentPage - 1) * couriersPerPage, courierCurrentPage * couriersPerPage).forEach(courier => {
            const row = tableBody.insertRow();
            row.insertCell(0).innerText = courier.Name || 'N/A';
            row.insertCell(1).innerText = courier.Joining_Date || 'N/A';
            row.insertCell(2).innerText = courier.Status || 'N/A';
            row.insertCell(3).innerText = courier.ID_Number || 'N/A';
            row.insertCell(4).innerText = courier.Sponsorshipstatus || 'N/A';

            row.addEventListener('click', () => fetchCourierDetails(courier.BARQ_ID));
        });

        document.getElementById('pageInfo').innerText = `Page ${courierCurrentPage} of ${Math.ceil(courierTotalCount / couriersPerPage)}`;
    }

    window.nextPage = function() {
        if ((courierCurrentPage * couriersPerPage) < courierTotalCount) {
            courierCurrentPage++;
            renderTable();
        }
    }

    window.previousPage = function() {
        if (courierCurrentPage > 1) {
            courierCurrentPage--;
            renderTable();
        }
    }

    function openModal(courier) {
        const modal = document.getElementById('courier-details');
        const courierDetails = document.getElementById('courierDetails');

        if (!courierDetails) {
            console.error('Courier details element not found.');
            return;
        }

        courierDetails.innerHTML = ''; // Clear previous content

        Object.keys(courier).forEach(key => {
            const detail = document.createElement('p');
            detail.innerText = `${key}: ${courier[key] || 'N/A'}`;
            courierDetails.appendChild(detail);
        });

        modal.classList.add('active'); // Show the sidebar
    }

    window.closeModal = function() {
        const modal = document.getElementById('courier-details');
        modal.classList.remove('active'); // Hide the sidebar
    }
});