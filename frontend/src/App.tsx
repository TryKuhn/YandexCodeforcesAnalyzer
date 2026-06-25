import {BrowserRouter, Routes, Route, Navigate} from 'react-router-dom';
import {Landing} from './pages/Landing';
import {LoginPage} from './pages/LoginPage';
import {RegisterPage} from './pages/RegisterPage';
import {useAuthStore} from './store/useAuthStore';
import {ThemeInitializer} from "./components/ThemeInitializer.tsx";
import {MainLayout} from "./components/layout/MainLayout.tsx";
import {AuthInitializer} from "./components/AuthInitializer.tsx";
import {Profile} from "./pages/Profile.tsx";
import {ChangePassword} from "./pages/ChangePassword.tsx";
import {YandexCallback} from "./pages/YandexCallback.tsx";
import {CodeforcesCallback} from "./pages/CodeforcesCallback.tsx";
import {LoadContestPage} from "./pages/LoadContestPage.tsx";
import {ContestsPage} from "./pages/ContestsPage.tsx";
import {ContestViewPage} from "./pages/ContestViewPage.tsx";
import {NotFound} from "./pages/NotFound.tsx";
import {ContestLayout} from "./components/layout/ContestLayout.tsx";
import {ContestOverview} from "./pages/ContestOverview.tsx";
import {ContestSubmissions} from "./pages/ContestSubmissions.tsx";
import {ContestAnalytics} from "./pages/ContestAnalytics.tsx";
import {TasksList} from "./pages/tasks/TasksList.tsx";
import {TaskPage} from "./pages/tasks/TaskPage.tsx";
import {FileEditorPage} from "./pages/tasks/FileEditorPage.tsx";
import {TestViewPage} from "./pages/tasks/TestViewPage.tsx";
import {ArchiveImportPage} from "./pages/ArchiveImportPage.tsx";
import {ImportSubmissions} from "./pages/ImportSubmissions.tsx";
import {SubmissionSource} from "./pages/SubmissionSource.tsx";
import {PlagiarismReport} from "./pages/PlagiarismReport.tsx";
import {PlagiarismComparison} from "./pages/PlagiarismComparation.tsx";
import {PlagiarismSetup} from "./pages/PlagiarismSetup.tsx";
import {DashboardHome} from "./pages/DashboardHome.tsx";
import {ContestVisualAnalytics} from "./pages/ContestVisualAnalytics.tsx";
import {Docs} from "./pages/Docs.tsx";

function App() {
    const {isAuthenticated} = useAuthStore();

    return (
        <BrowserRouter>
            <AuthInitializer/>
            <ThemeInitializer/>
            <Routes>
                <Route path="/login" element={isAuthenticated ? <Navigate to="/" replace/> : <LoginPage/>}/>
                <Route path="/register" element={isAuthenticated ? <Navigate to="/" replace/> : <RegisterPage/>}/>

                <Route path="/" element={isAuthenticated ? <MainLayout/> : <Landing/>}>
                    <Route index element={<DashboardHome/>}/>
                    <Route path="contests" element={<ContestsPage/>}/>
                    <Route path="contests/sync" element={<LoadContestPage/>}/>
                    <Route path="contests/:id" element={<ContestLayout/>}>
                        <Route index element={<ContestOverview/>}/>
                        <Route path="table" element={<ContestViewPage/>}/>
                        <Route path="submissions" element={<ContestSubmissions/>}/>
                        <Route path="/contests/:id/submissions/:subId" element={<SubmissionSource />} />
                        <Route path="import-submissions" element={<ImportSubmissions/>}/>
                        <Route path="analytics" element={<ContestAnalytics/>} />
                        <Route path="analytics/visual" element={<ContestVisualAnalytics/>} />
                        <Route path="analytics/check" element={<PlagiarismSetup />} />
                        <Route path="analytics/reports/:reportId" element={<PlagiarismReport />} />
                        <Route path="analytics/compare/:pairId" element={<PlagiarismComparison />} />
                    </Route>
                    <Route path="participants" element={<div>Страница участников</div>}/>
                    {/* Legacy AI-task flow removed — redirect old links to the new one. */}
                    <Route path="ai-tasks" element={<Navigate to="/tasks" replace/>}/>
                    <Route path="ai-tasks/:sessionId" element={<Navigate to="/tasks" replace/>}/>
                    <Route path="tasks" element={<TasksList/>}/>
                    <Route path="tasks/:polygonId" element={<TaskPage/>}/>
                    <Route path="tasks/:polygonId/files/:section/:name" element={<FileEditorPage/>}/>
                    <Route path="tasks/:polygonId/tests/:index/:kind" element={<TestViewPage/>}/>
                    <Route path="archive-import" element={<ArchiveImportPage/>}/>
                    <Route path="profile" element={<Profile/>}/>
                    <Route path="change-password" element={<ChangePassword/>}/>
                    <Route path="yandex/callback" element={<YandexCallback/>}/>
                    <Route path="codeforces/callback" element={<CodeforcesCallback/>}/>
                </Route>

                <Route path="/docs" element={<Docs/>}/>

                <Route path="*" element={<NotFound/>}/>
            </Routes>
        </BrowserRouter>
    );
}

export default App;
