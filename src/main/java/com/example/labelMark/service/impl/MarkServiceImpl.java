package com.example.labelMark.service.impl;

import com.example.labelMark.domain.Mark;
import com.example.labelMark.mapper.MarkMapper;
import com.example.labelMark.service.MarkService;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;

import java.sql.ResultSet;

/**
 * <p>
 *  服务实现类
 * </p>
 *
 * @author hjw
 * @since 2024-04-28
 */
@Service
public class MarkServiceImpl extends ServiceImpl<MarkMapper, Mark> implements MarkService {

    private MarkMapper markMapper;

    @Override
    public boolean isMark(int taskId, int userId) {
        int count = markMapper.isMark(taskId, userId);
        if(count != 0){
            return true;
        }else {
            return false;
        }
    }

    @Override
    public void createMark(int taskId, int userId, int typeId, String geom) {
        markMapper.createMark(taskId, userId, typeId, geom);
    }

    @Override
    public void deleteMark(int taskId, int userId,int typeId) {
        markMapper.deleteMark(taskId, userId, typeId);
    }

    @Override
    public void insertMark(Mark mark) {
//        Mark mark = new Mark();
//        mark.setTaskId(taskId);
//        mark.setUserId(userId);
//        mark.setGeom(geom);
        markMapper.insertMark(mark);
    }

    @Override
    public void deleteMarkByTaskId(int taskId) {
        markMapper.deleteMarkByTaskId(taskId);
    }

    @Override
    public Integer GetTaskIdNum(int taskId) {
        Integer num = markMapper.GetTaskIdNum(taskId);
        return num;
    }

//    @Override
//    public void createMark(String markName) {
//        markMapper.createMark(markName);
//    }
}
