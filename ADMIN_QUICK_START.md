# 👨‍💼 ADMIN WORKER MANAGEMENT - QUICK GUIDE

## 🚀 Quick Access

### Admin Login
```
URL: http://localhost:8000/login/
Username: testadmin
Password: admin123
```

### After Login - You'll See Dashboard with "Hi Admin" ✅

---

## 📋 Managing Workers

### Step 1: View All Workers
```
From Admin Dashboard:
  ✓ Click "👥 Manage Workers" card
  
OR direct:
  ✓ Go to: http://localhost:8000/manage-workers/
```

### Step 2: What You'll See
```
Table with columns:
  • Username
  • Email  
  • Country (assigned)
  • Data (assigned)
  • Dashboard URL (assigned)
  • Verified status
  • Edit button
```

### Step 3: Edit a Worker
```
Click "Edit" button next to the worker
  ↓
Edit page opens
```

---

## ✏️ Editing Worker Page

### Available Controls:

#### 1. 🌍 Assign Country (Dropdown)
```
Click dropdown
Select a country
No country = worker has no country assigned
```

#### 2. 📊 Assign Data (Dropdown)
```
Click dropdown
Select data entry
Shows: Data Name (Type)
No data = worker has no data assigned
```

#### 3. 🔗 Assign Dashboard URL (Dropdown)
```
Click dropdown
Select dashboard URL
Options include Worker/Admin dashboards
No URL = worker has default dashboard
```

#### 4. ✓ Verify Worker (Checkbox)
```
☐ Unchecked = Worker pending verification
✓ Checked = Worker approved/verified
```

---

## 💾 Save Changes

```
After making changes:
  1. Scroll to bottom
  2. Click "Save Changes" button
  3. You'll be redirected to worker list
  4. Confirmation message appears
```

---

## 🔄 Workflow Example

```
Step 1: Login as testadmin
Step 2: See "Hi Admin" dashboard
Step 3: Click "Manage Workers" 
Step 4: See list of workers (e.g., testworker)
Step 5: Click "Edit" next to testworker
Step 6: Select:
  - Country: "United States"
  - Data: "Employee Records"
  - Dashboard URL: "Worker Dashboard"
  - Verify checkbox
Step 7: Click "Save Changes"
Step 8: Back to worker list (confirmation shown)
```

---

## 📊 What Each Field Does

### Country Dropdown
```
Purpose: Assign geographic region to worker
Used For: Regional data management
Default: None (unassigned)
```

### Data Dropdown
```
Purpose: Assign data responsibility
Used For: Which data worker manages
Default: None (unassigned)
Contains: All data items from Data table
```

### Dashboard URL Dropdown
```
Purpose: Custom dashboard/URL for worker
Used For: Direct worker to specific page
Default: None (unassigned)
Options: Worker Dashboard, Admin Dashboard, etc.
```

### Verified Checkbox
```
Purpose: Admin approval status
Checked: Worker is verified/approved
Unchecked: Worker pending verification
Impact: May affect worker permissions
```

---

## ⚠️ Important Notes

✓ Only admins can access /manage-workers/
✓ Workers cannot change their own data/country
✓ Admins can modify any worker anytime
✓ All changes are saved immediately
✓ Timestamps track when changes were made

---

## 🔐 Admin-Only Features

```
✓ Manage all workers
✓ Assign countries
✓ Assign data
✓ Assign dashboard URLs
✓ Verify/unverify workers
✓ View all assignments
✗ Workers cannot use these features
```

---

## 🎯 Common Tasks

### Task: Add Country to Worker
```
1. Manage Workers
2. Edit [worker name]
3. Click Country dropdown
4. Select country
5. Save Changes ✓
```

### Task: Assign Data to Worker
```
1. Manage Workers
2. Edit [worker name]
3. Click Data dropdown
4. Select data
5. Save Changes ✓
```

### Task: Verify a Worker
```
1. Manage Workers
2. Edit [worker name]
3. Check "Verify this worker" checkbox
4. Save Changes ✓
  → Badge changes from "Pending" to "Verified"
```

### Task: Reassign Worker Data
```
1. Manage Workers
2. Edit [worker name]
3. Change Data dropdown to new data
4. Save Changes ✓
  → Worker now has new data assignment
```

---

## 📱 Mobile Responsive

✓ Table scrolls on mobile
✓ Forms stack nicely
✓ Dropdowns work on touch
✓ Buttons are large enough to tap

---

## 🔍 Status Badges

```
In Manage Workers table:

Country Column:
  🔵 "Country Name" = Assigned
  ⚠️ "Not Assigned" = No country

Data Column:
  🟢 "Data Name" = Assigned
  ⚠️ "Not Assigned" = No data

Dashboard URL Column:
  🔗 "URL Name" = Assigned
  ⚠️ "Not Assigned" = No URL

Verified Column:
  ✅ "Verified" = Approved
  ❌ "Pending" = Not approved
```

---

## 🚀 Quick Links

| Task | URL |
|------|-----|
| View Workers | `/manage-workers/` |
| Edit Worker (ID 1) | `/edit-worker/1/` |
| Dashboard | `/` |
| Profile | `/profile/` |
| Admin Panel | `/admin/` |

---

## 💡 Tips

- Use Admin Panel (/admin/) for bulk operations
- Use Manage Workers for quick verification
- Dashboard URL can be updated anytime
- Worker assignments don't affect login
- All changes are logged via timestamps

---

## ✅ Test It Now!

1. Login with: `testadmin` / `admin123`
2. Click "Manage Workers"
3. Click "Edit" on "testworker"
4. Select all dropdowns
5. Check verify box
6. Click "Save Changes"
7. ✅ Done!

---

**Status**: ✅ READY TO USE
**Last Updated**: Feb 28, 2026
