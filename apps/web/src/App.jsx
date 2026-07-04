import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { api } from './api';
import Layout from './components/Layout';
import LoginPage from './pages/Login';
import DashboardPage from './pages/Dashboard';
import QueuesPage from './pages/Queues';
import JobsPage from './pages/Jobs';
import JobDetailPage from './pages/JobDetail';
import WorkersPage from './pages/Workers';
import DlqPage from './pages/Dlq';
import ScheduledPage from './pages/Scheduled';

function ProtectedRoute({ children }) {
  const token = localStorage.getItem('access_token');
  if (!token) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          <Route index element={<DashboardPage />} />
          <Route path="queues" element={<QueuesPage />} />
          <Route path="jobs" element={<JobsPage />} />
          <Route path="jobs/:jobId" element={<JobDetailPage />} />
          <Route path="workers" element={<WorkersPage />} />
          <Route path="dlq" element={<DlqPage />} />
          <Route path="scheduled" element={<ScheduledPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
