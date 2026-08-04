import {Navigate, Route} from 'react-router-dom';
import {Trophy} from 'lucide-react';
import {JudgeContests} from '../pages/judge/JudgeContests.tsx';
import {JudgeScoreboard} from '../pages/judge/JudgeScoreboard.tsx';
import {JudgeSubmit} from '../pages/judge/JudgeSubmit.tsx';
import {Profile} from '../pages/Profile.tsx';
import {ChangePassword} from '../pages/ChangePassword.tsx';

/** What a contestant may see: contests, standings, own account. Nothing jury. */
export const portalRoutes = (
    <>
        <Route index element={<Navigate to="/contests" replace/>}/>
        <Route path="contests" element={<JudgeContests/>}/>
        <Route path="contests/:id" element={<JudgeScoreboard/>}/>
        <Route path="contests/:id/submit" element={<JudgeSubmit/>}/>
        <Route path="profile" element={<Profile/>}/>
        <Route path="change-password" element={<ChangePassword/>}/>
    </>
);

/** Contestants see only the contests they take part in. */
export const portalMenu = [
    {icon: Trophy, label: 'Соревнования', path: '/contests'},
];
