package com.example.labelMark.service;

import com.baomidou.mybatisplus.extension.service.IService;
import com.example.labelMark.domain.SysFile;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * <p>
 * 服务类
 * </p>
 *
 * @author hjw
 * @since 2024-04-18
 */
@Service
public interface SysFileService extends IService<SysFile> {

    List<SysFile> getAllFiles(Integer current, Integer pageSize, Integer fileId);

    void updateFile(Integer fileId, String fileName, String updateTime);

    void deleteFile(String fileName);

    void createFile(String fileName, String updateTime, String size);

    boolean updateFileStatus(String fileName);
}
