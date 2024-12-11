document.addEventListener('DOMContentLoaded', () => {
    const editProfileBtn = document.querySelector('.btn-edit-profile');
    
    if (editProfileBtn) {
        editProfileBtn.addEventListener('click', () => {
            // TODO: Implement profile editing functionality
            alert('Edit Profile feature coming soon!');
        });
    }

    // Optional: Add hover effect to achievement items
    const achievementItems = document.querySelectorAll('.achievement-item');
    achievementItems.forEach(item => {
        item.addEventListener('mouseenter', () => {
            item.style.transform = 'scale(1.02)';
        });
        
        item.addEventListener('mouseleave', () => {
            item.style.transform = 'scale(1)';
        });
    });
});
