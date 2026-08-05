import {Navigate, Route} from 'react-router-dom';
import {Archive, LayoutList, Trophy, Users} from 'lucide-react';
import {DashboardHome} from '../pages/DashboardHome.tsx';
import {ContestsPage} from '../pages/ContestsPage.tsx';
import {LoadContestPage} from '../pages/LoadContestPage.tsx';
import {ContestLayout} from '../components/layout/ContestLayout.tsx';
import {ContestOverview} from '../pages/ContestOverview.tsx';
import {ContestViewPage} from '../pages/ContestViewPage.tsx';
import {ContestSubmissions} from '../pages/ContestSubmissions.tsx';
import {SubmissionSource} from '../pages/SubmissionSource.tsx';
import {ImportSubmissions} from '../pages/ImportSubmissions.tsx';
import {ContestAnalytics} from '../pages/ContestAnalytics.tsx';
import {ContestVisualAnalytics} from '../pages/ContestVisualAnalytics.tsx';
import {PlagiarismSetup} from '../pages/PlagiarismSetup.tsx';
import {PlagiarismReport} from '../pages/PlagiarismReport.tsx';
import {PlagiarismComparison} from '../pages/PlagiarismComparation.tsx';
import {TasksList} from '../pages/tasks/TasksList.tsx';
import {TaskPage} from '../pages/tasks/TaskPage.tsx';
import {FileEditorPage} from '../pages/tasks/FileEditorPage.tsx';
import {TestViewPage} from '../pages/tasks/TestViewPage.tsx';
import {ArchiveImportPage} from '../pages/ArchiveImportPage.tsx';
import {Profile} from '../pages/Profile.tsx';
import {ChangePassword} from '../pages/ChangePassword.tsx';
import {YandexCallback} from '../pages/YandexCallback.tsx';
import {CodeforcesCallback} from '../pages/CodeforcesCallback.tsx';
import {JudgeContests} from '../pages/judge/JudgeContests.tsx';
import {JudgeScoreboard} from '../pages/judge/JudgeScoreboard.tsx';
import {JudgeSubmit} from '../pages/judge/JudgeSubmit.tsx';

/** Everything the jury works with; plagiarism, AI authoring and imports live here only. */
export const portalRoutes = (
    <>
        <Route index element={<DashboardHome/>}/>
        <Route path="contests" element={<ContestsPage/>}/>
        <Route path="contests/sync" element={<LoadContestPage/>}/>
        <Route path="contests/:id" element={<ContestLayout/>}>
            <Route index element={<ContestOverview/>}/>
            <Route path="table" element={<ContestViewPage/>}/>
            <Route path="submissions" element={<ContestSubmissions/>}/>
            <Route path="/contests/:id/submissions/:subId" element={<SubmissionSource/>}/>
            <Route path="import-submissions" element={<ImportSubmissions/>}/>
            <Route path="analytics" element={<ContestAnalytics/>}/>
            <Route path="analytics/visual" element={<ContestVisualAnalytics/>}/>
            <Route path="analytics/check" element={<PlagiarismSetup/>}/>
            <Route path="analytics/reports/:reportId" element={<PlagiarismReport/>}/>
            <Route path="analytics/compare/:pairId" element={<PlagiarismComparison/>}/>
        </Route>

        <Route path="judge/contests" element={<JudgeContests/>}/>
        <Route path="judge/contests/:id" element={<JudgeScoreboard/>}/>
        <Route path="judge/contests/:id/submit" element={<JudgeSubmit/>}/>

        <Route path="participants" element={<div>Страница участников</div>}/>
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
    </>
);

/** Top navigation for the jury build. */
export const portalMenu = [
    {icon: Trophy, label: 'Соревнования', path: '/contests'},
    {icon: Users, label: 'Участники', path: '/participants'},
    {icon: LayoutList, label: 'Задачи', path: '/tasks'},
    {icon: Archive, label: 'Импорт архива', path: '/archive-import'},
];
