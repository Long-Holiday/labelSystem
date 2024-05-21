package com.example.labelMark.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.example.labelMark.domain.TaskAccepted;
import com.example.labelMark.domain.sysFile;
import com.example.labelMark.mapper.TaskAcceptedMapper;
import com.example.labelMark.mapper.TaskMapper;
import com.example.labelMark.service.TaskAcceptedService;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;

/**
 * <p>
 *  服务实现类
 * </p>
 *
 * @author hjw
 * @since 2024-04-25
 */
@Service
public class TaskAcceptedServiceImpl extends ServiceImpl<TaskAcceptedMapper, TaskAccepted> implements TaskAcceptedService {

    private TaskAcceptedMapper taskAcceptedMapper;

    @Override
    public boolean createTaskAccept(Integer taskId, String username, String typeArr) {
        TaskAccepted taskAccepted = new TaskAccepted();
        taskAccepted.setTaskId(taskId);
        taskAccepted.setUsername(username);
        taskAccepted.setTypeArr(typeArr);
        boolean isSave = save(taskAccepted);
//        taskAcceptedMapper.createTaskAccept(taskId, username, typeArr);
        return isSave;
    }

    @Override
    public void deleteTaskAcceptById(int id) {


        taskAcceptedMapper.deleteTaskAcceptById(id);

    }
}
