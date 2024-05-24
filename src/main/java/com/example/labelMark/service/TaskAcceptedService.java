package com.example.labelMark.service;

import com.example.labelMark.domain.TaskAccepted;
import com.baomidou.mybatisplus.extension.service.IService;
import org.springframework.stereotype.Service;

/**
 * <p>
 *  服务类
 * </p>
 *
 * @author hjw
 * @since 2024-04-25
 */
@Service
public interface TaskAcceptedService extends IService<TaskAccepted> {

    boolean createTaskAccept(Integer taskId, String username, String typeArr);

    void deleteTaskAcceptByTaskId(int id);
}
